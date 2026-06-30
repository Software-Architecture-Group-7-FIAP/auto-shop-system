from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://oficina:replace-with-local-password@localhost:5432/oficina"
    app_env: str = "development"
    secret_key: SecretStr = Field(..., min_length=32)
    algorithm: str = "HS256"
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
    cors_allow_credentials: bool = True
    security_hsts_enabled: bool = False
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_login_requests: int = 10
    rate_limit_public_requests: int = 30
    invertexto_api_token: str = ""
    dev_admin_password: str | None = None
    dev_admin_email: str = "admin@oficina.local"

    @field_validator("secret_key", mode="before")
    @classmethod
    def reject_unsafe_secret_key(cls, value: str) -> str:
        unsafe_values = {
            "",
            "dev-secret-key",
            "change-me",
            "replace-with-at-least-32-random-characters",
            "replace-with-at-least-32-random-characters-not-this-value",
            "change-me-in-production-use-a-long-random-string",
            "dev-secret-key-change-in-production",
        }
        if value in unsafe_values:
            raise ValueError("SECRET_KEY must be set to a strong secret via environment")
        return value

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
            if not (self.smtp_use_tls or self.smtp_starttls):
                raise ValueError("SMTP TLS is required in production-like environments")
            if self.cors_allow_credentials and "*" in self.cors_origins():
                raise ValueError("Wildcard CORS is unsafe with credentials enabled")
        if self.smtp_use_tls and self.smtp_starttls:
            raise ValueError("SMTP_USE_TLS and SMTP_STARTTLS are mutually exclusive")
        return self

    def jwt_secret(self) -> str:
        return self.secret_key.get_secret_value()

    def smtp_password_value(self) -> str | None:
        return self.smtp_password.get_secret_value() if self.smtp_password else None

    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    def is_production_like(self) -> bool:
        return self.app_env.lower() in {"production", "prod", "staging"}


settings = Settings()
