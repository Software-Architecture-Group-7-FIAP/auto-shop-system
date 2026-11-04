"""Run one privacy-bounded HML customer-authentication request."""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


ALLOWED_HOST = "api.oficina-workshop.com.br"
ALLOWED_PATH = "/hml/auth/customer/token"
DEFAULT_URL = f"https://{ALLOWED_HOST}{ALLOWED_PATH}"
CPF_PATTERN = re.compile(r"^[0-9]{11}$")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class SyntheticAuthError(RuntimeError):
    """Raised when the bounded synthetic request cannot be performed safely."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _default_opener(request: Request, timeout: float):
    opener = build_opener(_RejectRedirects)
    return opener.open(request, timeout=timeout)


def _validate_target(url: str) -> None:
    target = urlsplit(url)
    if (
        target.scheme != "https"
        or target.hostname != ALLOWED_HOST
        or target.port not in (None, 443)
        or target.path != ALLOWED_PATH
        or target.query
        or target.fragment
    ):
        raise SyntheticAuthError("Synthetic authentication target is not the approved HML endpoint.")


def _discard_body(response: Any) -> None:
    response.read(65536)


def _safe_request_id(value: Any) -> str:
    candidate = value if isinstance(value, str) else ""
    return candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else "unavailable"


def run_synthetic_auth(
    *,
    url: str,
    cpf: str,
    opener: Callable[..., Any] = _default_opener,
) -> dict[str, str | int]:
    _validate_target(url)
    if not CPF_PATTERN.fullmatch(cpf):
        raise SyntheticAuthError("The synthetic customer document must contain exactly 11 digits.")

    correlation_id = str(uuid4())
    request = Request(
        url=url,
        data=json.dumps({"cpf": cpf}, separators=(",", ":")).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Observability-Run-ID": correlation_id,
        },
        method="POST",
    )

    try:
        with opener(request, timeout=10.0) as response:
            _discard_body(response)
            status = int(response.status)
            request_id = _safe_request_id(response.headers.get("x-amzn-requestid"))
    except HTTPError as error:
        _discard_body(error)
        if 300 <= error.code < 400:
            raise SyntheticAuthError("Synthetic authentication redirects are forbidden.") from error
        status = int(error.code)
        request_id = _safe_request_id(error.headers.get("x-amzn-requestid"))
    except (OSError, ssl.SSLError) as error:
        raise SyntheticAuthError("Synthetic authentication transport failed.") from error

    if status != 200:
        raise SyntheticAuthError(f"Synthetic authentication returned HTTP {status}.")

    return {
        "status": status,
        "correlation_id": correlation_id,
        "gateway_request_id": request_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    cpf = os.environ.get("HML_SYNTHETIC_CUSTOMER_CPF", "")
    result = run_synthetic_auth(url=args.url, cpf=cpf)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
