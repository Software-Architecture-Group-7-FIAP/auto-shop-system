import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import boto3
import psycopg2
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

MIGRATION_LOCK_KEY = 7_349_841
ALLOWED_PG_QUERY_PARAMETERS = frozenset({"sslmode", "sslrootcert"})
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
        raise TypeError("Migration database credentials are invalid")

    username = secret.get("username")
    password = secret.get("password")
    host = secret.get("host")
    port = secret.get("port")
    if not all(
        isinstance(value, str) and value for value in (username, password, host, port)
    ):
        raise RuntimeError("Migration database credentials are invalid")

    expected_environment = {
        "autoshop_hml": "hml",
        "autoshop_prd": "prd",
    }.get(database_name)
    if (
        expected_environment is None
        or username != f"autoshop_migrations_{expected_environment}"
    ):
        raise RuntimeError("Migration database credentials are invalid")

    try:
        port_number = int(port)
    except ValueError:
        raise RuntimeError("Migration database credentials are invalid") from None
    if not 1 <= port_number <= 65535:
        raise RuntimeError("Migration database credentials are invalid")

    return URL.create(
        "postgresql",
        username=username,
        password=password,
        host=host,
        port=port_number,
        database=database_name,
        query={
            "sslmode": "verify-full",
            "sslrootcert": str(RDS_CA_BUNDLE),
        },
    ).render_as_string(hide_password=False)


def _migration_config() -> tuple[str, int, bool]:
    if os.environ.get("MIGRATION_DATABASE_SECRET_ARN"):
        return _load_migration_database_url(), 2, True

    if os.environ.get("APP_ENV", "").lower() in {"staging", "production", "prod"}:
        raise RuntimeError("Migration database configuration is incomplete")

    from src.config import settings

    return settings.database_url, settings.database_health_check_timeout_seconds, False


def _psycopg2_connection_arguments(database_url: str) -> dict[str, object]:
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+psycopg2"} or not url.database:
        raise RuntimeError("Migration database configuration is invalid")
    if set(url.query) - ALLOWED_PG_QUERY_PARAMETERS:
        raise RuntimeError("Migration database configuration is invalid")

    arguments: dict[str, object] = {
        "dbname": url.database,
        "host": url.host,
        "user": url.username,
        "password": url.password,
        "port": url.port,
    }
    for key, value in url.query.items():
        if not isinstance(value, str) or not value:
            raise RuntimeError("Migration database configuration is invalid")
        arguments[key] = value
    return {key: value for key, value in arguments.items() if value is not None}


def _classify_connection_failure(error: Exception) -> tuple[str, bool, str | None]:
    message = str(error).lower()
    sqlstate = getattr(error, "pgcode", None)

    if sqlstate and (sqlstate.startswith("08") or sqlstate == "57P03"):
        if sqlstate == "57P03":
            return "database server is not accepting connections yet", True, sqlstate
        return "database connection was interrupted", True, sqlstate

    if any(
        marker in message
        for marker in (
            "connection refused",
            "connection timed out",
            "timeout expired",
            "could not translate host name",
            "temporary failure in name resolution",
            "name or service not known",
            "no route to host",
            "network is unreachable",
            "server closed the connection unexpectedly",
            "the database system is starting up",
            "cannot connect now",
        )
    ):
        if (
            "translate host name" in message
            or "name resolution" in message
            or "service not known" in message
        ):
            summary = "database hostname could not be resolved"
        elif "refused" in message:
            summary = "database connection was refused"
        elif "timeout" in message or "timed out" in message:
            summary = "database connection timed out"
        elif "route to host" in message or "network is unreachable" in message:
            summary = "database network path is unavailable"
        elif "starting up" in message or "cannot connect now" in message:
            summary = "database server is not accepting connections yet"
        else:
            summary = "database connection was interrupted"
        return summary, True, sqlstate

    if "password authentication failed" in message or "no password supplied" in message:
        return "database rejected migration credentials", False, sqlstate
    if "certificate" in message or "ssl error" in message:
        return "database TLS certificate validation failed", False, sqlstate
    return "database connection failed", False, sqlstate


def run_migrations() -> int:
    try:
        database_url, connect_timeout, use_migration_identity = _migration_config()
        connection_arguments = _psycopg2_connection_arguments(database_url)
    except (ArgumentError, RuntimeError, TypeError) as error:
        print(
            f"migration preflight: invalid database configuration ({type(error).__name__})",
            file=sys.stderr,
            flush=True,
        )
        return 20

    try:
        connection = psycopg2.connect(
            **connection_arguments,
            connect_timeout=connect_timeout,
        )
    except (OSError, psycopg2.Error) as error:
        summary, retryable, sqlstate = _classify_connection_failure(error)
        sqlstate_message = f"; sqlstate={sqlstate}" if sqlstate else ""
        print(
            f"migration preflight: {summary} ({type(error).__name__}; "
            f"retryable={str(retryable).lower()}{sqlstate_message})",
            file=sys.stderr,
            flush=True,
        )
        return 10 if retryable else 20

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
                lock_acquired = bool(cursor.fetchone()[0])
            if not lock_acquired:
                print(
                    "migration failed: another migration is already holding the database advisory lock",
                    file=sys.stderr,
                    flush=True,
                )
                return 20
            print(
                "migration preflight: database connected and advisory lock acquired; applying Alembic revisions",
                flush=True,
            )
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
