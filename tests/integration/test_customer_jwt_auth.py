import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from src.config import settings

ISSUER = "https://auth.example.invalid"
AUDIENCE = "auto-shop-api"


@pytest.fixture
def customer_token_factory(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_id = f"test-{uuid4().hex}"
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": key_id, "use": "sig", "alg": "RS256"})
    jwks = {"keys": [jwk]}

    monkeypatch.setattr(PyJWKClient, "fetch_data", lambda _client: jwks)
    monkeypatch.setattr(
        settings,
        "customer_jwt_jwks_url",
        f"https://auth.example.invalid/{key_id}",
    )
    monkeypatch.setattr(settings, "customer_jwt_issuer", ISSUER)
    monkeypatch.setattr(settings, "customer_jwt_audience", AUDIENCE)
    monkeypatch.setattr(settings, "customer_jwt_clock_skew_seconds", 0)
    monkeypatch.setattr(settings, "customer_jwt_jwks_timeout_seconds", 2)
    monkeypatch.setattr(settings, "customer_jwt_jwks_cache_seconds", 300)

    def create_token(_headers=None, _missing_claim: str | None = None, **overrides):
        now = datetime.now(timezone.utc)
        claims = {
            "sub": "42",
            "principal_type": "customer",
            "scope": "customer",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
            "jti": "test-token-id",
        }
        claims.update(overrides)
        if _missing_claim is not None:
            claims.pop(_missing_claim)
        return jwt.encode(
            claims,
            private_key,
            algorithm="RS256",
            headers=_headers if _headers is not None else {"kid": key_id},
        )

    return create_token


def test_customer_me_returns_only_the_authenticated_internal_id(
    client,
    customer_token_factory,
):
    token = customer_token_factory()

    response = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"customer_id": 42}
    assert "cpf" not in response.text.lower()
    assert "email" not in response.text.lower()


def test_customer_me_fails_closed_when_jwt_configuration_is_missing(client, monkeypatch):
    monkeypatch.setattr(settings, "customer_jwt_jwks_url", None)
    monkeypatch.setattr(settings, "customer_jwt_issuer", None)
    monkeypatch.setattr(settings, "customer_jwt_audience", None)

    response = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": "Bearer opaque-token"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Autentica\u00e7\u00e3o temporariamente indispon\u00edvel"
    )


def test_customer_me_returns_service_unavailable_when_jwks_cannot_be_loaded(
    client,
    customer_token_factory,
    monkeypatch,
):
    token = customer_token_factory()

    def fail_to_load_jwks(_client):
        raise PyJWKClientConnectionError("offline")

    monkeypatch.setattr(PyJWKClient, "fetch_data", fail_to_load_jwks)
    response = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Autentica\u00e7\u00e3o temporariamente indispon\u00edvel"
    )


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("exp", datetime.now(timezone.utc) - timedelta(minutes=1)),
        ("iss", "https://wrong-issuer.example.invalid"),
        ("aud", "another-api"),
        ("scope", "admin"),
        ("principal_type", "admin"),
        ("sub", "not-a-customer-id"),
        ("sub", "042"),
        ("jti", ""),
    ],
)
def test_customer_me_rejects_invalid_claims(client, customer_token_factory, claim, value):
    if claim == "exp":
        value = int(value.timestamp())
    token = customer_token_factory(**{claim: value})

    response = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciais inv\u00e1lidas"


def test_customer_me_rejects_missing_and_non_bearer_tokens(client, customer_token_factory):
    token = customer_token_factory()

    without_token = client.get("/api/v1/customer/me")
    wrong_scheme = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": f"Basic {token}"},
    )

    assert without_token.status_code == 401
    assert wrong_scheme.status_code == 401


@pytest.mark.parametrize(
    "missing_claim",
    ("sub", "principal_type", "scope", "iss", "aud", "iat", "exp", "jti"),
)
def test_customer_me_rejects_each_missing_required_claim(
    client,
    customer_token_factory,
    missing_claim,
):
    token = customer_token_factory(_missing_claim=missing_claim)

    response = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciais inv\u00e1lidas"


def test_customer_me_does_not_accept_admin_cookie_as_customer_identity(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert login.status_code == 200
    assert client.cookies.get("oficina_access")

    response = client.get("/api/v1/customer/me")
    client.cookies.clear()

    assert response.status_code == 401


def test_customer_me_rejects_tampered_and_unsupported_algorithm_tokens(
    client,
    customer_token_factory,
):
    valid_token = customer_token_factory()
    header, payload, signature = valid_token.split(".")
    tampered_token = f"{header}.{payload}.{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"
    unsupported_algorithm = jwt.encode(
        {"sub": "42", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "irrelevant-test-secret-with-32-bytes-minimum",
        algorithm="HS256",
    )

    for token in (tampered_token, unsupported_algorithm):
        response = client.get(
            "/api/v1/customer/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


def test_customer_me_rejects_rs256_token_without_key_id(client, customer_token_factory):
    token = customer_token_factory(_headers={})

    response = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_admin_token_does_not_authenticate_as_customer(client, customer_token_factory):
    customer_token_factory()
    login = client.post(
        "/api/v1/auth/gateway-login",
        json={"username": "admin", "password": "admin123"},
    )
    assert login.status_code == 200
    admin_token = login.json()["access_token"]

    response = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 401


def test_customer_token_does_not_authenticate_as_admin(client, customer_token_factory):
    customer_token = customer_token_factory()

    response = client.get(
        "/api/v1/admin/customers",
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    assert response.status_code == 401


def test_invalid_customer_token_is_not_written_to_application_logs(
    client,
    customer_token_factory,
    caplog,
):
    token = customer_token_factory()
    header, payload, signature = token.split(".")
    tampered_token = f"{header}.{payload}.{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"

    response = client.get(
        "/api/v1/customer/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )

    assert response.status_code == 401
    assert tampered_token not in caplog.text
    assert "52998224725" not in caplog.text
