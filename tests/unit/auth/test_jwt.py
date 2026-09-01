from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.config import settings
from src.domain.exceptions import UnauthorizedError
from src.infrastructure.auth.jwt import JwtAccessTokenService


def test_access_token_round_trip_uses_hs256():
    token = JwtAccessTokenService().create_access_token("admin")

    header = jwt.get_unverified_header(token)

    assert header["alg"] == "HS256"
    assert JwtAccessTokenService().decode_token(token) == "admin"


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
