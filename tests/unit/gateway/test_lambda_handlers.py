import importlib.util
import sys
import time
from pathlib import Path
from unittest.mock import patch

import jwt
import pytest

ROOT = Path(__file__).resolve().parents[3]
FUNCTIONS = ROOT / "gateway" / "functions"


def _load_handler(relative_path: str, module_name: str):
    path = FUNCTIONS / relative_path / "handler.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


jwt_authorizer_module = _load_handler("jwt_authorizer", "gateway_jwt_authorizer")
jwt_authorizer_handler = jwt_authorizer_module.handler


def test_jwt_authorizer_allows_valid_token():
    secret = "unit-test-secret-key-with-32-chars-min"
    token = jwt.encode(
        {
            "sub": "admin",
            "sid": "session-1",
            "exp": int(time.time()) + 300,
            "aud": "gateway",
        },
        secret,
        algorithm="HS256",
    )
    with patch.object(jwt_authorizer_module, "_jwt_secret", return_value=secret):
        policy = jwt_authorizer_handler(
            {
                "authorizationToken": f"Bearer {token}",
                "methodArn": "arn:aws:execute-api:region:acct:api/stage/GET/admin",
            },
            None,
        )
    assert policy["principalId"] == "admin"
    assert policy["policyDocument"]["Statement"][0]["Effect"] == "Allow"


def test_jwt_authorizer_rejects_invalid_token():
    with patch.object(
        jwt_authorizer_module,
        "_jwt_secret",
        return_value="unit-test-secret-key-with-32-chars-min",
    ):
        with pytest.raises(Exception, match="Unauthorized"):
            jwt_authorizer_handler(
                {
                    "authorizationToken": "Bearer invalid",
                    "methodArn": "arn:aws:execute-api:region:acct:api/stage/GET/admin",
                },
                None,
            )


def _encode_token(secret: str, audience: str) -> str:
    return jwt.encode(
        {
            "sub": "admin",
            "sid": "session-1",
            "exp": int(time.time()) + 300,
            "aud": audience,
        },
        secret,
        algorithm="HS256",
    )


def test_jwt_authorizer_accepts_request_bearer_header():
    secret = "unit-test-secret-key-with-32-chars-min"
    token = _encode_token(secret, "gateway")
    event = {
        "headers": {"Authorization": f"Bearer {token}"},
        "methodArn": "arn:aws:execute-api:region:acct:api/stage/GET/admin",
    }

    with patch.object(jwt_authorizer_module, "_jwt_secret", return_value=secret):
        policy = jwt_authorizer_handler(event, None)

    assert policy["principalId"] == "admin"
    assert policy["policyDocument"]["Statement"][0]["Effect"] == "Allow"


def test_jwt_authorizer_accepts_web_session_cookie():
    secret = "unit-test-secret-key-with-32-chars-min"
    token = _encode_token(secret, "web")
    event = {
        "headers": {"cookie": f"theme=dark; oficina_access={token}"},
        "methodArn": "arn:aws:execute-api:region:acct:api/stage/GET/admin",
    }

    with patch.object(jwt_authorizer_module, "_jwt_secret", return_value=secret):
        policy = jwt_authorizer_handler(event, None)

    assert policy["principalId"] == "admin"
    assert policy["policyDocument"]["Statement"][0]["Effect"] == "Allow"


def test_jwt_authorizer_rejects_gateway_token_from_cookie():
    secret = "unit-test-secret-key-with-32-chars-min"
    token = _encode_token(secret, "gateway")
    event = {
        "headers": {"Cookie": f"oficina_access={token}"},
        "methodArn": "arn:aws:execute-api:region:acct:api/stage/GET/admin",
    }

    with patch.object(jwt_authorizer_module, "_jwt_secret", return_value=secret):
        with pytest.raises(Exception, match="Unauthorized"):
            jwt_authorizer_handler(event, None)
