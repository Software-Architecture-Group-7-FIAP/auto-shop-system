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
        "replace-with-at-least-32-random-characters-not-this-value",
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


def test_settings_rejects_plaintext_smtp_in_production():
    with pytest.raises(ValidationError, match="SMTP TLS is required"):
        Settings(
            secret_key="strong-test-secret-with-at-least-32-chars",
            app_env="production",
            smtp_use_tls=False,
            smtp_starttls=False,
            _env_file=None,
        )


PRODUCTION_PURPOSE_SECRETS = {
    "access_token_secret": "production-access-secret-with-32-chars",
    "refresh_token_pepper": "production-refresh-pepper-with-32-chars",
    "budget_approval_token_secret": "production-approval-secret-with-32-chars",
    "tracking_token_secret": "production-tracking-secret-with-32-chars",
}


def test_settings_accepts_starttls_smtp_in_production():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        app_env="production",
        smtp_starttls=True,
        invertexto_api_token="test-token",
        _env_file=None,
        **PRODUCTION_PURPOSE_SECRETS,
    )

    assert settings.smtp_starttls is True


def test_settings_requires_invertexto_token_in_production():
    with pytest.raises(ValidationError, match="INVERTEXTO_API_TOKEN is required"):
        Settings(
            secret_key="strong-test-secret-with-at-least-32-chars",
            app_env="production",
            smtp_starttls=True,
            invertexto_api_token="",
            _env_file=None,
        )


def test_settings_parses_cors_origins():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        cors_allowed_origins="https://app.example.com, https://admin.example.com",
        _env_file=None,
    )

    assert settings.cors_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
