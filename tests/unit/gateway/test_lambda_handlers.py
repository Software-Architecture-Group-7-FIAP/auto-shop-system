import importlib.util
import json
import os
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
    return module.handler


auth_login_handler = _load_handler("auth_login", "gateway_auth_login")
jwt_authorizer_handler = _load_handler("jwt_authorizer", "gateway_jwt_authorizer")


def test_auth_login_rejects_invalid_json():
    response = auth_login_handler({"body": "not-json"}, None)
    assert response["statusCode"] == 400


@patch.dict(os.environ, {"BACKEND_BASE_URL": "http://backend.test"})
def test_auth_login_requires_credentials():
    response = auth_login_handler({"body": json.dumps({})}, None)
    assert response["statusCode"] == 400


@patch.dict(os.environ, {"JWT_SECRET": "unit-test-secret-key-with-32-chars-min"})
def test_jwt_authorizer_allows_valid_token():
    secret = "unit-test-secret-key-with-32-chars-min"
    token = jwt.encode(
        {"sub": "admin", "sid": "session-1", "exp": int(time.time()) + 300},
        secret,
        algorithm="HS256",
    )
    policy = jwt_authorizer_handler(
        {
            "authorizationToken": f"Bearer {token}",
            "methodArn": "arn:aws:execute-api:region:acct:api/stage/GET/admin",
        },
        None,
    )
    assert policy["principalId"] == "admin"
    assert policy["policyDocument"]["Statement"][0]["Effect"] == "Allow"


@patch.dict(os.environ, {"JWT_SECRET": "unit-test-secret-key-with-32-chars-min"})
def test_jwt_authorizer_rejects_invalid_token():
    with pytest.raises(Exception, match="Unauthorized"):
        jwt_authorizer_handler(
            {
                "authorizationToken": "Bearer invalid",
                "methodArn": "arn:aws:execute-api:region:acct:api/stage/GET/admin",
            },
            None,
        )
