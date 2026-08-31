from datetime import datetime, timedelta, timezone

import pytest
import jwt

from src.config import settings
from src.infrastructure.auth.jwt import JWT_ALGORITHM
from src.infrastructure.auth.tokens import (
    create_signed_approval_token,
    validate_approval_token,
)


def test_signed_approval_token_includes_expiration():
    token = create_signed_approval_token(123)

    payload = jwt.decode(token, settings.jwt_secret(), algorithms=[JWT_ALGORITHM])

    assert payload["budget_id"] == 123
    assert payload["type"] == "budget_approval"
    assert "exp" in payload


def test_validate_approval_token_accepts_valid_token():
    token = create_signed_approval_token(123)

    assert validate_approval_token(token) == 123


def test_validate_approval_token_rejects_expired_token():
    token = jwt.encode(
        {
            "budget_id": 123,
            "type": "budget_approval",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        settings.jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(ValueError, match="Invalid approval token"):
        validate_approval_token(token)


def test_validate_approval_token_rejects_wrong_token_type():
    token = jwt.encode(
        {
            "budget_id": 123,
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(ValueError, match="Invalid token type"):
        validate_approval_token(token)


def test_validate_approval_token_rejects_token_without_expiration():
    token = jwt.encode(
        {"budget_id": 123, "type": "budget_approval"},
        settings.jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(ValueError, match="Missing expiration"):
        validate_approval_token(token)


def test_validate_approval_token_rejects_invalid_budget_id():
    token = jwt.encode(
        {
            "budget_id": "123",
            "type": "budget_approval",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(ValueError, match="Invalid budget id"):
        validate_approval_token(token)


def test_validate_approval_token_rejects_malformed_token():
    with pytest.raises(ValueError, match="Invalid approval token"):
        validate_approval_token("not-a-jwt")
