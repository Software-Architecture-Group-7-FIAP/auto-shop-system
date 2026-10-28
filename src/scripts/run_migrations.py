import json
import os
import secrets
import subprocess
from pathlib import Path

import boto3
import psycopg2
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.engine import URL


MIGRATION_LOCK_KEY = 7_349_841
RDS_CA_BUNDLE = (
    Path(__file__).resolve().parents[1]
    / "infrastructure"
    / "certs"
    / "rds-us-east-1-bundle.pem"
)


def _load_migration_database_url() -> str:
    secret_arn = os.environ.get("MIGRATION_DATABASE_SECRET_ARN")
    database_name = os.environ.get("MIGRATION_DATABASE_NAME")
    if not secret_arn or not database_name:
        raise RuntimeError("Migration database configuration is incomplete")

    try:
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        response = boto3.client("secretsmanager", region_name=region).get_secret_value(
            SecretId=secret_arn
        )
        secret = json.loads(response["SecretString"])
    except (BotoCoreError, ClientError, KeyError, TypeError, json.JSONDecodeError):
        raise RuntimeError("Migration database credentials are unavailable") from None

    if not isinstance(secret, dict):
        raise RuntimeError("Migration database credentials are invalid")

    username = secret.get("username")
    password = secret.get("password")
    host = secret.get("host")
    port = secret.get("port")
    if not all((username, password, host, port)):
        raise RuntimeError("Migration database credentials are invalid")

    return URL.create(
        "postgresql",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=database_name,
        query={
            "sslmode": "verify-full",
            "sslrootcert": str(RDS_CA_BUNDLE),
        },
    ).render_as_string(hide_password=False)


def _migration_config() -> tuple[str, int, bool]:
    if os.environ.get("MIGRATION_DATABASE_SECRET_ARN"):
        return _load_migration_database_url(), 2, True

    from src.config import settings

    return settings.database_url, settings.database_health_check_timeout_seconds, False


def run_migrations() -> int:
    database_url, connect_timeout, use_migration_identity = _migration_config()

    try:
        connection = psycopg2.connect(
            database_url,
            connect_timeout=connect_timeout,
        )
    except (psycopg2.Error, OSError):
        return 10

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
            if use_migration_identity:
                migration_env = os.environ.copy()
                migration_env.update(
                    {
                        "DATABASE_URL": database_url,
                        "APP_ENV": "development",
                        "SECRET_KEY": secrets.token_urlsafe(48),
                    }
                )
                result = subprocess.run(
                    ["alembic", "upgrade", "head"],
                    check=False,
                    env=migration_env,
                )
            else:
                result = subprocess.run(["alembic", "upgrade", "head"], check=False)
            return result.returncode
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(run_migrations())
