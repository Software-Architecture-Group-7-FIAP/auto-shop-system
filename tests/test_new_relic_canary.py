from __future__ import annotations

import io
import struct
import unittest
from contextlib import redirect_stderr, redirect_stdout
from urllib.error import HTTPError
from urllib.request import Request

from scripts.observability.new_relic_canary import (
    CanaryRequestError,
    OTLP_ENDPOINTS,
    _RejectRedirectHandler,
    build_otlp_metrics_request,
    main,
    send_canary,
)


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7


def _read_message(data: bytes) -> dict[int, list[tuple[int, bytes | int]]]:
    fields: dict[int, list[tuple[int, bytes | int]]] = {}
    offset = 0
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        field_number, wire_type = tag >> 3, tag & 0x07
        if wire_type == 1:
            value: bytes | int = data[offset : offset + 8]
            offset += 8
        elif wire_type == 2:
            length, offset = _read_varint(data, offset)
            value = data[offset : offset + length]
            offset += length
        else:
            raise AssertionError(f"Unexpected wire type {wire_type} in canary payload.")
        fields.setdefault(field_number, []).append((wire_type, value))
    return fields


def _one_bytes_field(fields: dict[int, list[tuple[int, bytes | int]]], number: int) -> bytes:
    values = fields[number]
    if len(values) != 1 or values[0][0] != 2:
        raise AssertionError(f"Expected one length-delimited field {number}.")
    value = values[0][1]
    if not isinstance(value, bytes):
        raise AssertionError(f"Field {number} was not bytes.")
    return value


def _one_fixed64_field(fields: dict[int, list[tuple[int, bytes | int]]], number: int) -> bytes:
    values = fields[number]
    if len(values) != 1 or values[0][0] != 1:
        raise AssertionError(f"Expected one fixed64 field {number}.")
    value = values[0][1]
    if not isinstance(value, bytes):
        raise AssertionError(f"Field {number} was not bytes.")
    return value


def _string_from_key_value(data: bytes) -> tuple[str, str]:
    fields = _read_message(data)
    key = _one_bytes_field(fields, 1).decode("utf-8")
    value_fields = _read_message(_one_bytes_field(fields, 2))
    value = _one_bytes_field(value_fields, 1).decode("utf-8")
    return key, value


class FakeResponse:
    status = 200

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class NewRelicCanaryTests(unittest.TestCase):
    def test_request_contains_only_synthetic_hml_attributes_and_one_point(self) -> None:
        run_id = "123456-1"
        timestamp = 1_798_000_000_000_000_000
        payload = build_otlp_metrics_request(run_id=run_id, timestamp_unix_nano=timestamp)

        request_fields = _read_message(payload)
        resource_metrics = _read_message(_one_bytes_field(request_fields, 1))
        resource = _read_message(_one_bytes_field(resource_metrics, 1))
        resource_attributes = [
            _string_from_key_value(value)
            for wire_type, value in resource[1]
            if wire_type == 2 and isinstance(value, bytes)
        ]
        self.assertEqual(
            resource_attributes,
            [
                ("service.name", "auto-shop-ingest-canary"),
                ("deployment.environment", "hml"),
            ],
        )

        scope_metrics = _read_message(_one_bytes_field(resource_metrics, 2))
        metric = _read_message(_one_bytes_field(scope_metrics, 2))
        self.assertEqual(_one_bytes_field(metric, 1), b"auto_shop_new_relic_ingest_canary")
        gauge = _read_message(_one_bytes_field(metric, 5))
        self.assertEqual(len(gauge[1]), 1)
        point = _read_message(_one_bytes_field(gauge, 1))
        self.assertEqual(int.from_bytes(_one_fixed64_field(point, 3), "little"), timestamp)
        self.assertEqual(struct.unpack("<d", _one_fixed64_field(point, 4))[0], 1.0)
        self.assertEqual(
            _string_from_key_value(_one_bytes_field(point, 7)),
            ("canary.run_id", run_id),
        )
        self.assertLessEqual(len(payload), 2_048)
        self.assertNotIn(b"cpf", payload.lower())
        self.assertNotIn(b"cnpj", payload.lower())

    def test_sends_one_request_to_the_selected_otlp_region(self) -> None:
        requests: list[Request] = []

        def fake_opener(request: Request, *, timeout: int) -> FakeResponse:
            requests.append(request)
            self.assertEqual(timeout, 10)
            return FakeResponse()

        status = send_canary(
            license_key="example-license-key",
            region="eu",
            run_id="123456-1",
            opener=fake_opener,
        )

        self.assertEqual(status, 200)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].full_url, f"{OTLP_ENDPOINTS['eu']}/v1/metrics")
        self.assertEqual(requests[0].method, "POST")
        self.assertEqual(requests[0].get_header("Api-key"), "example-license-key")
        self.assertEqual(requests[0].get_header("Content-type"), "application/x-protobuf")
        self.assertNotIn(b"example-license-key", requests[0].data)

    def test_rejects_missing_license_key_before_network_call(self) -> None:
        def fail_if_called(*args: object, **kwargs: object) -> FakeResponse:
            raise AssertionError("network must not be called without a key")

        with self.assertRaisesRegex(ValueError, "NEW_RELIC_LICENSE_KEY is required"):
            send_canary(
                license_key=" ",
                region="us",
                run_id="123456-1",
                opener=fail_if_called,
            )

    def test_rejects_invalid_license_key_characters_without_echoing_value(self) -> None:
        secret = "unsafe\nlicense-value"
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(
                ["--region", "us", "--run-id", "123456-1"],
                environ={"NEW_RELIC_LICENSE_KEY": secret},
                opener=lambda *args, **kwargs: self.fail("network must not be called"),
            )

        self.assertEqual(exit_code, 2)
        self.assertIn("printable ASCII", stderr.getvalue())
        self.assertNotIn(secret, stderr.getvalue())

    def test_redirects_are_rejected(self) -> None:
        handler = _RejectRedirectHandler()
        request = Request(
            f"{OTLP_ENDPOINTS['us']}/v1/metrics",
            headers={"api-key": "example-license-key"},
        )

        redirected_request = handler.redirect_request(
            request,
            io.BytesIO(),
            307,
            "temporary redirect",
            {},
            "https://untrusted.example/v1/metrics",
        )

        self.assertIsNone(redirected_request)

    def test_sanitizes_http_error_without_printing_response_body_or_key(self) -> None:
        secret = "license-value-must-not-be-logged"
        response = io.BytesIO(f"rejected {secret}".encode("utf-8"))

        def fail_with_http_error(request: Request, *, timeout: int) -> FakeResponse:
            raise HTTPError(request.full_url, 403, secret, hdrs=None, fp=response)

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(
                ["--region", "us", "--run-id", "123456-1"],
                environ={"NEW_RELIC_LICENSE_KEY": secret},
                opener=fail_with_http_error,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("HTTP 403", stderr.getvalue())
        self.assertNotIn(secret, stderr.getvalue())

    def test_success_message_does_not_claim_nrql_visibility(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                ["--region", "us", "--run-id", "123456-1"],
                environ={"NEW_RELIC_LICENSE_KEY": "example-license-key"},
                opener=lambda request, *, timeout: FakeResponse(),
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("verify metric arrival", stdout.getvalue())
        self.assertIn("canary_run_id=123456-1", stdout.getvalue())
        self.assertNotIn("example-license-key", stdout.getvalue())

    def test_request_error_is_sanitized(self) -> None:
        with self.assertRaises(CanaryRequestError):
            send_canary(
                license_key="example-license-key",
                region="us",
                run_id="123456-1",
                opener=lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()),
            )


if __name__ == "__main__":
    unittest.main()
