from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


EnvironmentName = Literal["development", "local", "test", "staging", "production", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://oficina:replace-with-local-password@localhost:5432/oficina"
    app_env: EnvironmentName = "production"
    secret_key: SecretStr = Field(..., min_length=32)
    algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = 15
    access_token_secret: SecretStr | None = None
    refresh_token_pepper: SecretStr | None = None
    refresh_token_expire_days: int = 7
    login_max_attempts: int = 10
    login_attempt_window_seconds: int = 300
    login_lockout_seconds: int = 900
    login_rate_limit_max_buckets: int = 10_000
    public_rate_limit_max_requests: int = 30
    public_rate_limit_window_seconds: int = 60
    public_rate_limit_max_buckets: int = 10_000
    redis_url: str | None = None
    budget_approval_token_expire_hours: int = 72
    budget_approval_token_secret: SecretStr | None = None
    tracking_token_secret: SecretStr | None = None
    tracking_token_expire_days: int = 7
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: SecretStr | None = None
    smtp_from: str = "noreply@oficina.local"
    smtp_use_tls: bool = False
    smtp_starttls: bool = False
    smtp_require_tls: bool = False
    app_base_url: str = "http://localhost:8000"
    frontend_public_url: str = "http://localhost:4200"
    cors_allowed_origins: str = "http://localhost:4200"
    cors_allowed_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_allowed_headers: str = "Authorization,Content-Type,X-CSRF-Token,X-Request-ID,Accept"
    cors_allow_credentials: bool = True
    security_hsts_enabled: bool = False
    invertexto_api_token: str = ""
    skip_cpf_external_validation: bool = False
    dev_admin_password: str | None = None
    dev_admin_email: str = "admin@oficina.local"
    auto_create_schema: bool = False
    database_health_check_timeout_seconds: int = Field(default=2, ge=1, le=10)

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in {"development", "local", "test", "staging", "production", "prod"}:
            raise ValueError("APP_ENV must be one of development, local, test, staging, production, or prod")
        return normalized

    @field_validator("secret_key", mode="before")
    @classmethod
    def reject_unsafe_secret_key(cls, value: str | SecretStr) -> str:
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        normalized_value = raw_value.strip().lower()
        unsafe_values = {
            "dev-secret-key",
            "change-me",
            "replace-with-at-least-32-random-characters",
            "replace-with-at-least-32-random-characters-not-this-value",
            "change-me-in-production-use-a-long-random-string",
            "dev-secret-key-change-in-production",
        }
        if not normalized_value or normalized_value in unsafe_values:
            raise ValueError("SECRET_KEY must be set to a strong secret via environment")
        return raw_value

    @field_validator("dev_admin_password", mode="before")
    @classmethod
    def empty_dev_admin_password_disables_seed(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("smtp_password", mode="before")
    @classmethod
    def empty_smtp_password_is_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator(
        "access_token_secret",
        "refresh_token_pepper",
        "budget_approval_token_secret",
        "tracking_token_secret",
        mode="before",
    )
    @classmethod
    def validate_purpose_secret(cls, value: SecretStr | str | None) -> SecretStr | str | None:
        if value is None or value == "":
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if len(raw) < 32 or "replace-with" in raw or "change-me" in raw:
            raise ValueError("Purpose-specific secrets must contain at least 32 random characters")
        return value

    @model_validator(mode="after")
    def validate_security_sensitive_settings(self) -> "Settings":
        if self.is_production_like():
            if not self.cors_origins() or "*" in self.cors_origins():
                raise ValueError("Production-like CORS requires an explicit origin allowlist")
            if "*" in self.cors_methods() or "*" in self.cors_headers():
                raise ValueError("Production-like CORS requires explicit methods and headers")
            self._validate_production_urls()
            if not self._is_configured_database_url():
                raise ValueError("DATABASE_URL must be a configured non-placeholder PostgreSQL URL")
            if (
                not self.smtp_user.strip()
                or self._is_placeholder(self.smtp_user)
                or self.smtp_password_value() is None
                or self._is_placeholder(self.smtp_password_value())
            ):
                raise ValueError("SMTP authentication is required in production-like environments")
            if not (self.smtp_use_tls or self.smtp_starttls):
                raise ValueError("SMTP TLS is required in production-like environments")
            if not self.smtp_require_tls:
                raise ValueError("SMTP_REQUIRE_TLS must be enabled in production-like environments")
            if self.smtp_host.strip().lower() in {"localhost", "mailhog"}:
                raise ValueError("SMTP host must be external in production-like environments")
            if self._is_placeholder(self.invertexto_api_token):
                raise ValueError("INVERTEXTO_API_TOKEN is required in production-like environments")
            if self.auto_create_schema:
                raise ValueError("AUTO_CREATE_SCHEMA must be disabled in production-like environments")
            if not self.access_token_secret:
                raise ValueError("ACCESS_TOKEN_SECRET is required in production-like environments")
            if not self.refresh_token_pepper:
                raise ValueError("REFRESH_TOKEN_PEPPER is required in production-like environments")
            if not self.budget_approval_token_secret:
                raise ValueError(
                    "BUDGET_APPROVAL_TOKEN_SECRET is required in production-like environments"
                )
            if not self.tracking_token_secret:
                raise ValueError("TRACKING_TOKEN_SECRET is required in production-like environments")
            if not self.redis_url:
                raise ValueError("REDIS_URL is required in production-like environments")
        if self.smtp_use_tls and self.smtp_starttls:
            raise ValueError("SMTP_USE_TLS and SMTP_STARTTLS are mutually exclusive")
        if self.smtp_require_tls and not (self.smtp_use_tls or self.smtp_starttls):
            raise ValueError("SMTP_REQUIRE_TLS requires SMTP_USE_TLS or SMTP_STARTTLS")
        return self

    @staticmethod
    def _is_placeholder(value: str | None) -> bool:
        if not value:
            return True
        normalized = value.strip().lower()
        if normalized in {"password", "senha"}:
            return True
        return any(
            marker in normalized
            for marker in (
                "replace-with",
                "change-me",
                "your_",
                "your-",
                "seu_",
                "sua_",
                "example.com",
            )
        )

    def _is_configured_database_url(self) -> bool:
        parsed = urlparse(self.database_url)
        if parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg2"}:
            return False
        if not parsed.hostname or not parsed.username or not parsed.password:
            return False
        return not self._is_placeholder(parsed.username) and not self._is_placeholder(parsed.password)

    def _validate_production_urls(self) -> None:
        urls = [self.app_base_url, self.frontend_public_url, *self.cors_origins()]
        if any(
            urlparse(url).scheme != "https" or not urlparse(url).hostname
            for url in urls
        ):
            raise ValueError("Production-like URLs must use HTTPS")

    def jwt_secret(self) -> str:
        return self.secret_key.get_secret_value()

    def access_token_secret_value(self) -> str:
        return self.access_token_secret.get_secret_value() if self.access_token_secret else self.jwt_secret()

    def refresh_token_pepper_value(self) -> str:
        return self.refresh_token_pepper.get_secret_value() if self.refresh_token_pepper else self.jwt_secret()

    def budget_approval_secret(self) -> str:
        return (
            self.budget_approval_token_secret.get_secret_value()
            if self.budget_approval_token_secret
            else self.jwt_secret()
        )

    def tracking_secret(self) -> str:
        return (
            self.tracking_token_secret.get_secret_value()
            if self.tracking_token_secret
            else self.jwt_secret()
        )

    def smtp_password_value(self) -> str | None:
        return self.smtp_password.get_secret_value() if self.smtp_password else None

    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    def cors_methods(self) -> list[str]:
        return [method.strip() for method in self.cors_allowed_methods.split(",") if method.strip()]

    def cors_headers(self) -> list[str]:
        return [header.strip() for header in self.cors_allowed_headers.split(",") if header.strip()]

    def request_origins(self) -> list[str]:
        """Origins allowed to send state-changing requests.

        The app serves its own legacy panel from ``app_base_url``, so that
        origin is always trusted in addition to the configured CORS list.
        """
        origins = self.cors_origins()
        own_origin = self.own_origin()
        if own_origin and own_origin not in origins:
            origins = origins + [own_origin]
        return origins

    def own_origin(self) -> str | None:
        parsed = urlparse(self.app_base_url)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"

    def is_production_like(self) -> bool:
        """Deny by default: anything not explicitly a dev environment is prod.

        A typo such as ``APP_ENV=prd`` must not silently drop the ``Secure``
        cookie flag or skip the production validations below.
        """
        return self.app_env.lower() not in {
            "development",
            "dev",
            "local",
            "test",
            "testing",
        }


settings = Settings()
