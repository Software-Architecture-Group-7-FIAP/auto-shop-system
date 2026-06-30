from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://oficina:oficina@localhost:5432/oficina"
    secret_key: str = "dev-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@oficina.local"
    app_base_url: str = "http://localhost:8000"
    frontend_public_url: str = "http://localhost:4200"
    invertexto_api_token: str = ""
    skip_cpf_external_validation: bool = False


settings = Settings()
