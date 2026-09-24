"""TOKEN Lambda authorizer for HS256 JWT used by API Gateway."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def _jwt_algorithm() -> str:
    return os.environ.get("JWT_ALGORITHM", "HS256")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _verify_hs256(token: str, secret: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise ValueError("Malformed JWT") from exc

    header = json.loads(_b64url_decode(header_b64))
    if header.get("alg") != _jwt_algorithm():
        raise ValueError("Unsupported JWT algorithm")

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    provided_signature = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Invalid JWT signature")

    claims = json.loads(_b64url_decode(payload_b64))
    exp = claims.get("exp")
    if not isinstance(exp, int) or exp <= int(time.time()):
        raise ValueError("JWT expired")
    if not claims.get("sub"):
        raise ValueError("JWT missing subject")
    return claims


def _policy(principal_id: str, effect: str, resource: str, context: dict[str, str]) -> dict[str, Any]:
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
        "context": context,
    }


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    token = event.get("authorizationToken") or ""
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        raise Exception("Unauthorized")

    method_arn = event["methodArn"]
    try:
        claims = _verify_hs256(token, _jwt_secret())
    except ValueError as exc:
        raise Exception("Unauthorized") from exc

    context = {
        "username": str(claims.get("sub", "")),
        "sessionId": str(claims.get("sid", "")),
    }
    return _policy(context["username"], "Allow", method_arn, context)
