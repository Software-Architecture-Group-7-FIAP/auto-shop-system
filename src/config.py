from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://oficina:oficina@localhost:5432/oficina"
    secret_key: SecretStr = Field(..., min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    budget_approval_token_expire_hours: int = 72
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@oficina.local"
    app_base_url: str = "http://localhost:8000"
    frontend_public_url: str = "http://localhost:4200"
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

    def jwt_secret(self) -> str:
        return self.secret_key.get_secret_value()


settings = Settings()
