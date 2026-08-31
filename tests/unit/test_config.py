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


def test_settings_rejects_whitespace_secret_key():
    with pytest.raises(ValidationError, match="SECRET_KEY must be set"):
        Settings(secret_key=" " * 32, app_env="development", _env_file=None)


def test_settings_rejects_unknown_environment():
    with pytest.raises(ValidationError, match="APP_ENV must be one of"):
        Settings(
            secret_key="strong-test-secret-with-at-least-32-chars",
            app_env="prodution",
            _env_file=None,
        )


def test_settings_defaults_to_secure_production_environment(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(secret_key="strong-test-secret-with-at-least-32-chars", _env_file=None)


def test_settings_exposes_jwt_secret_value():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        app_env="development",
        _env_file=None,
    )

    assert settings.jwt_secret() == "strong-test-secret-with-at-least-32-chars"


def test_settings_treats_empty_dev_admin_password_as_disabled():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        app_env="development",
        dev_admin_password="",
        _env_file=None,
    )

    assert settings.dev_admin_password is None


def test_settings_exposes_dev_admin_password():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        app_env="development",
        dev_admin_password="safe-dev-password",
        _env_file=None,
    )

    assert settings.dev_admin_password == "safe-dev-password"


def test_settings_rejects_plaintext_smtp_in_production():
    with pytest.raises(ValidationError, match="SMTP TLS is required"):
        Settings(
            secret_key="strong-test-secret-with-at-least-32-chars",
            app_env="production",
            database_url="postgresql://app:strong-db-secret@db.internal:5432/oficina",
            app_base_url="https://api.example.com",
            frontend_public_url="https://app.example.com",
            cors_allowed_origins="https://app.example.com",
            smtp_user="smtp-user",
            smtp_password="strong-smtp-secret",
            smtp_use_tls=False,
            smtp_starttls=False,
            _env_file=None,
        )


def test_settings_accepts_starttls_smtp_in_production():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        app_env="production",
        database_url="postgresql://app:strong-db-secret@db.internal:5432/oficina",
        app_base_url="https://api.example.com",
        frontend_public_url="https://app.example.com",
        cors_allowed_origins="https://app.example.com",
        smtp_user="smtp-user",
        smtp_password="strong-smtp-secret",
        smtp_host="smtp.relay.internal",
        smtp_starttls=True,
        smtp_require_tls=True,
        invertexto_api_token="test-token",
        _env_file=None,
    )

    assert settings.smtp_starttls is True


def test_production_requires_smtp_require_tls_flag():
    with pytest.raises(ValidationError, match="SMTP_REQUIRE_TLS"):
        production_settings(smtp_require_tls=False)


def test_settings_rejects_subsecond_database_timeout():
    with pytest.raises(ValidationError):
        Settings(
            secret_key="strong-test-secret-with-at-least-32-chars",
            app_env="development",
            database_health_check_timeout_seconds=0.5,
            _env_file=None,
        )


def test_settings_requires_invertexto_token_in_production():
    with pytest.raises(ValidationError, match="INVERTEXTO_API_TOKEN is required"):
        Settings(
            secret_key="strong-test-secret-with-at-least-32-chars",
            app_env="production",
            database_url="postgresql://app:strong-db-secret@db.internal:5432/oficina",
            app_base_url="https://api.example.com",
            frontend_public_url="https://app.example.com",
            cors_allowed_origins="https://app.example.com",
            smtp_user="smtp-user",
            smtp_password="strong-smtp-secret",
            smtp_host="smtp.relay.internal",
            smtp_starttls=True,
            smtp_require_tls=True,
            invertexto_api_token="",
            _env_file=None,
        )


def test_settings_parses_cors_origins():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        app_env="development",
        cors_allowed_origins="https://app.example.com, https://admin.example.com",
        _env_file=None,
    )

    assert settings.cors_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def production_settings(**overrides):
    values = {
        "secret_key": "strong-test-secret-with-at-least-32-chars",
        "app_env": "production",
        "database_url": "postgresql://app:strong-db-secret@db.internal:5432/oficina",
        "app_base_url": "https://api.example.com",
        "frontend_public_url": "https://app.example.com",
        "cors_allowed_origins": "https://app.example.com",
        "smtp_user": "smtp-user",
        "smtp_password": "strong-smtp-secret",
        "smtp_host": "smtp.relay.internal",
        "smtp_starttls": True,
        "smtp_require_tls": True,
        "invertexto_api_token": "live-invertexto-token",
        "_env_file": None,
    }
    return Settings(**{**values, **overrides})


def test_production_rejects_http_urls():
    with pytest.raises(ValidationError, match="HTTPS"):
        production_settings(app_base_url="http://api.example.com")


def test_production_rejects_placeholder_database_url():
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        production_settings(database_url="postgresql://user:replace-with-password@db:5432/oficina")


def test_production_requires_authenticated_smtp():
    with pytest.raises(ValidationError, match="SMTP authentication"):
        production_settings(smtp_user="", smtp_password=None)


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError, match="explicit origin allowlist"):
        production_settings(cors_allowed_origins="*")


def test_development_allows_explicit_local_urls_and_mailhog():
    settings = Settings(
        secret_key="strong-test-secret-with-at-least-32-chars",
        app_env="development",
        app_base_url="http://localhost:8000",
        frontend_public_url="http://localhost:4200",
        cors_allowed_origins="http://localhost:4200",
        smtp_host="mailhog",
        _env_file=None,
    )

    assert settings.app_env == "development"
    assert settings.smtp_host == "mailhog"


def test_settings_rejects_non_hs256_algorithm():
    with pytest.raises(ValidationError):
        Settings(
            secret_key="strong-test-secret-with-at-least-32-chars",
            app_env="development",
            algorithm="HS384",
            _env_file=None,
        )
