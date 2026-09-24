"""API Gateway Lambda proxy for public authentication."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

def _backend_base_url() -> str:
    return os.environ["BACKEND_BASE_URL"].rstrip("/")


def _backend_login_path() -> str:
    return os.environ.get("BACKEND_LOGIN_PATH", "/api/v1/auth/gateway-login")


def _request_timeout_seconds() -> int:
    return int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10"))


def _max_retries() -> int:
    return int(os.environ.get("MAX_RETRIES", "2"))


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body),
    }


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        raw_body = base64.b64decode(raw_body).decode("utf-8")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def _call_backend(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url=f"{_backend_base_url()}{_backend_login_path()}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    last_error: urllib.error.HTTPError | urllib.error.URLError | None = None
    for attempt in range(_max_retries() + 1):
        try:
            with urllib.request.urlopen(request, timeout=_request_timeout_seconds()) as response:
                response_body = response.read().decode("utf-8")
                return response.status, json.loads(response_body or "{}")
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8")
            try:
                parsed = json.loads(response_body or "{}")
            except json.JSONDecodeError:
                parsed = {"message": response_body or exc.reason}
            if exc.code < 500 or attempt == _max_retries():
                return exc.code, parsed
            last_error = exc
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == _max_retries():
                break
    message = "Authentication backend unavailable"
    if isinstance(last_error, urllib.error.HTTPError):
        message = last_error.reason or message
    elif isinstance(last_error, urllib.error.URLError):
        message = str(last_error.reason or last_error)
    return 503, {"message": message}


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    try:
        payload = _parse_body(event)
    except ValueError as exc:
        return _response(400, {"message": str(exc)})

    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        return _response(400, {"message": "username and password are required"})

    status_code, body = _call_backend({"username": username, "password": password})
    return _response(status_code, body)
