from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.config import settings
from src.domain.exceptions import UnauthorizedError
from src.infrastructure.auth.jwt import JWT_AUD_GATEWAY, JWT_AUD_WEB, JwtAccessTokenService


def test_access_token_round_trip_uses_hs256():
    token = JwtAccessTokenService().create_access_token("admin")

    header = jwt.get_unverified_header(token)

    assert header["alg"] == "HS256"
    assert JwtAccessTokenService().decode_token(token) == "admin"


def test_access_token_includes_audience_claim():
    service = JwtAccessTokenService()
    web_token = service.create_access_token("admin", "session-1")
    gateway_token = service.create_access_token(
        "admin",
        "session-1",
        audience=JWT_AUD_GATEWAY,
    )

    web_claims = service.decode_claims(web_token)
    gateway_claims = service.decode_claims(gateway_token)

    assert web_claims["aud"] == JWT_AUD_WEB
    assert gateway_claims["aud"] == JWT_AUD_GATEWAY


def test_access_token_rejects_expired_token():
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        settings.jwt_secret(),
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError):
        JwtAccessTokenService().decode_token(token)


def test_access_token_rejects_invalid_signature():
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
        "wrong-key",
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError):
        JwtAccessTokenService().decode_token(token)


def test_access_token_rejects_unexpected_algorithm():
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
        settings.jwt_secret(),
        algorithm="HS384",
    )

    with pytest.raises(UnauthorizedError):
        JwtAccessTokenService().decode_token(token)


def test_access_token_rejects_missing_subject():
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
        settings.jwt_secret(),
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError):
        JwtAccessTokenService().decode_token(token)


def test_access_token_rejects_missing_expiration():
    token = jwt.encode(
        {"sub": "admin"},
        settings.jwt_secret(),
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError):
        JwtAccessTokenService().decode_token(token)
