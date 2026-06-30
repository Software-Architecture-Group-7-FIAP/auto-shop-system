import pytest
from pydantic import ValidationError

from src.config import Settings


def test_settings_requires_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="Field required"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "unsafe_secret",
    [
        "",
        "dev-secret-key",
        "change-me",
        "replace-with-at-least-32-random-characters",
        "change-me-in-production-use-a-long-random-string",
        "dev-secret-key-change-in-production",
    ],
)
def test_settings_rejects_unsafe_secret_key(unsafe_secret: str):
    with pytest.raises(ValidationError, match="SECRET_KEY must be set"):
        Settings(secret_key=unsafe_secret, _env_file=None)


def test_settings_rejects_short_secret_key():
    with pytest.raises(ValidationError):
        Settings(secret_key="short-secret", _env_file=None)


def test_settings_exposes_jwt_secret_value():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        _env_file=None,
    )

    assert settings.jwt_secret() == "strong-test-secret-with-at-least-32-chars"


def test_settings_treats_empty_dev_admin_password_as_disabled():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        dev_admin_password="",
        _env_file=None,
    )

    assert settings.dev_admin_password is None


def test_settings_exposes_dev_admin_password():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        dev_admin_password="safe-dev-password",
        _env_file=None,
    )

    assert settings.dev_admin_password == "safe-dev-password"
