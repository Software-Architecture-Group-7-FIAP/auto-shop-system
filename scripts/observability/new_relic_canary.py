"""Send one synthetic HML metric over New Relic's OTLP/HTTP endpoint."""

from __future__ import annotations

import argparse
import os
import re
import struct
import sys
import time
import uuid
from collections.abc import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


OTLP_ENDPOINTS = {
    "us": "https://otlp.nr-data.net",
    "eu": "https://otlp.eu01.nr-data.net",
    "jp": "https://otlp.jp.nr-data.net",
}
SERVICE_NAME = "auto-shop-ingest-canary"
ENVIRONMENT_NAME = "hml"
METRIC_NAME = "auto_shop_new_relic_ingest_canary"
INSTRUMENTATION_SCOPE = "auto-shop.observability.canary"
MAX_REQUEST_BYTES = 2_048
REQUEST_TIMEOUT_SECONDS = 10
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class CanaryRequestError(RuntimeError):
    """A sanitized failure while sending a canary request."""


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("Protobuf varints must be non-negative.")

    encoded = bytearray()
    while value > 0x7F:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _encode_bytes_field(field_number: int, value: bytes) -> bytes:
    tag = (field_number << 3) | 2
    return _encode_varint(tag) + _encode_varint(len(value)) + value


def _encode_string_field(field_number: int, value: str) -> bytes:
    return _encode_bytes_field(field_number, value.encode("utf-8"))


def _encode_fixed64_uint_field(field_number: int, value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("Protobuf fixed64 value is outside its supported range.")
    tag = (field_number << 3) | 1
    return _encode_varint(tag) + struct.pack("<Q", value)


def _encode_fixed64_double_field(field_number: int, value: float) -> bytes:
    tag = (field_number << 3) | 1
    return _encode_varint(tag) + struct.pack("<d", value)


def _encode_key_value(key: str, value: str) -> bytes:
    any_value = _encode_string_field(1, value)
    return _encode_string_field(1, key) + _encode_bytes_field(2, any_value)


def build_otlp_metrics_request(*, run_id: str, timestamp_unix_nano: int) -> bytes:
    """Build a minimal OTLP ExportMetricsServiceRequest with one gauge point."""
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Canary run ID must contain 1-64 letters, digits, underscores, or hyphens.")
    if timestamp_unix_nano <= 0:
        raise ValueError("Canary timestamp must be a positive Unix nanosecond value.")

    # These protobuf field numbers follow the stable OTLP metric messages:
    # ExportMetricsServiceRequest, ResourceMetrics, ScopeMetrics, Metric,
    # Gauge, NumberDataPoint, Resource, KeyValue, AnyValue, and InstrumentationScope.
    resource = b"".join(
        (
            _encode_bytes_field(1, _encode_key_value("service.name", SERVICE_NAME)),
            _encode_bytes_field(
                1,
                _encode_key_value("deployment.environment", ENVIRONMENT_NAME),
            ),
        )
    )
    instrumentation_scope = _encode_string_field(1, INSTRUMENTATION_SCOPE)
    data_point = b"".join(
        (
            _encode_fixed64_uint_field(3, timestamp_unix_nano),
            _encode_fixed64_double_field(4, 1.0),
            _encode_bytes_field(7, _encode_key_value("canary.run_id", run_id)),
        )
    )
    gauge = _encode_bytes_field(1, data_point)
    metric = b"".join(
        (
            _encode_string_field(1, METRIC_NAME),
            _encode_bytes_field(5, gauge),
        )
    )
    scope_metrics = b"".join(
        (
            _encode_bytes_field(1, instrumentation_scope),
            _encode_bytes_field(2, metric),
        )
    )
    resource_metrics = b"".join(
        (
            _encode_bytes_field(1, resource),
            _encode_bytes_field(2, scope_metrics),
        )
    )
    request_body = _encode_bytes_field(1, resource_metrics)
    if len(request_body) > MAX_REQUEST_BYTES:
        raise ValueError("Canary request exceeds the fixed 2 KiB payload limit.")
    return request_body


def _resolve_run_id(run_id: str | None, environ: Mapping[str, str]) -> str:
    if run_id:
        resolved = run_id
    elif environ.get("GITHUB_RUN_ID"):
        attempt = environ.get("GITHUB_RUN_ATTEMPT", "1")
        resolved = f"{environ['GITHUB_RUN_ID']}-{attempt}"
    else:
        resolved = uuid.uuid4().hex

    if not RUN_ID_PATTERN.fullmatch(resolved):
        raise ValueError("Canary run ID must contain 1-64 letters, digits, underscores, or hyphens.")
    return resolved


def send_canary(
    *,
    license_key: str,
    region: str,
    run_id: str,
    opener: Callable[..., object] | None = None,
) -> int:
    if not license_key.strip():
        raise ValueError("NEW_RELIC_LICENSE_KEY is required.")
    if not all(0x21 <= ord(character) <= 0x7E for character in license_key):
        raise ValueError("NEW_RELIC_LICENSE_KEY must be printable ASCII without spaces or control characters.")
    if region not in OTLP_ENDPOINTS:
        raise ValueError("New Relic region must be one of: us, eu, jp.")

    request_body = build_otlp_metrics_request(
        run_id=run_id,
        timestamp_unix_nano=time.time_ns(),
    )
    request = Request(
        url=f"{OTLP_ENDPOINTS[region]}/v1/metrics",
        data=request_body,
        headers={
            "Accept": "application/x-protobuf",
            "Content-Type": "application/x-protobuf",
            "api-key": license_key,
        },
        method="POST",
    )

    send_request = opener or build_opener(_RejectRedirectHandler()).open
    try:
        with send_request(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
        error.close()
        raise CanaryRequestError(f"New Relic OTLP endpoint returned HTTP {status}.") from None
    except (URLError, TimeoutError, OSError):
        raise CanaryRequestError("Could not complete the request to the New Relic OTLP endpoint.") from None

    if status != 200:
        raise CanaryRequestError(f"New Relic OTLP endpoint returned HTTP {status}.")
    return status


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    opener: Callable[..., object] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Send one synthetic HML metric to New Relic OTLP.")
    parser.add_argument("--region", choices=tuple(OTLP_ENDPOINTS), required=True)
    parser.add_argument("--run-id")
    arguments = parser.parse_args(argv)
    environment = os.environ if environ is None else environ

    try:
        run_id = _resolve_run_id(arguments.run_id, environment)
        status = send_canary(
            license_key=environment.get("NEW_RELIC_LICENSE_KEY", ""),
            region=arguments.region,
            run_id=run_id,
            opener=opener,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    except CanaryRequestError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"New Relic OTLP endpoint returned HTTP {status}; verify metric arrival in New Relic.")
    print(f"canary_run_id={run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
