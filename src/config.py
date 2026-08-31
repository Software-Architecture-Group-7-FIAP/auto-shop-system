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
    access_token_expire_minutes: int = 60
    budget_approval_token_expire_hours: int = 72
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
    cors_allowed_headers: str = "Authorization,Content-Type"
    cors_allow_credentials: bool = True
    security_hsts_enabled: bool = False
    invertexto_api_token: str = ""
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

    def smtp_password_value(self) -> str | None:
        return self.smtp_password.get_secret_value() if self.smtp_password else None

    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    def cors_methods(self) -> list[str]:
        return [method.strip() for method in self.cors_allowed_methods.split(",") if method.strip()]

    def cors_headers(self) -> list[str]:
        return [header.strip() for header in self.cors_allowed_headers.split(",") if header.strip()]

    def is_production_like(self) -> bool:
        return self.app_env.lower() in {"production", "prod", "staging"}
    skip_cpf_external_validation: bool = False


settings = Settings()
