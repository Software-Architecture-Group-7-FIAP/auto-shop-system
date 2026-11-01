import json
from pathlib import Path
from unittest.mock import Mock, patch

import psycopg2
import pytest
from sqlalchemy.engine import make_url

from src.scripts.run_migrations import (
    MIGRATION_LOCK_KEY,
    _load_migration_database_url,
    _migration_config,
    run_migrations,
)


class FakeConnection:
    def __init__(self):
        self.cursor_instance = Mock()
        self.cursor_instance.__enter__ = Mock(return_value=self.cursor_instance)
        self.cursor_instance.__exit__ = Mock(return_value=False)
        self.cursor_instance.fetchone = Mock(return_value=(True,))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        return None


def test_run_migrations_holds_database_advisory_lock():
    connection = FakeConnection()
    completed = Mock(returncode=0)

    with (
        patch(
            "src.scripts.run_migrations._migration_config",
            return_value=(
                "postgresql+psycopg2://user:password@localhost:5432/testdb",
                5,
                False,
            ),
        ),
        patch("src.scripts.run_migrations.psycopg2.connect", return_value=connection),
        patch(
            "src.scripts.run_migrations.subprocess.run", return_value=completed
        ) as run,
    ):
        assert run_migrations() == 0

    connection.cursor_instance.execute.assert_called_once_with(
        "SELECT pg_try_advisory_lock(%s)", (MIGRATION_LOCK_KEY,)
    )
    run.assert_called_once_with(["alembic", "upgrade", "head"], check=False)


def test_run_migrations_uses_libpq_arguments_for_escaped_credentials():
    connection = FakeConnection()
    completed = Mock(returncode=0)
    database_url = (
        "postgresql+psycopg2://autoshop_migrations_hml:test-password%3A%2F%25%3F%23"
        "@db.example.us-east-1.rds.amazonaws.com:5432/autoshop_hml"
        "?sslmode=verify-full&sslrootcert=%2Fetc%2Fssl%2Frds%20ca.pem"
    )

    with (
        patch(
            "src.scripts.run_migrations._migration_config",
            return_value=(database_url, 2, True),
        ),
        patch(
            "src.scripts.run_migrations.psycopg2.connect",
            return_value=connection,
        ) as connect,
        patch("src.scripts.run_migrations.subprocess.run", return_value=completed),
    ):
        assert run_migrations() == 0

    connect.assert_called_once_with(
        dbname="autoshop_hml",
        host="db.example.us-east-1.rds.amazonaws.com",
        user="autoshop_migrations_hml",
        password="test-password:/%?#",
        port=5432,
        sslmode="verify-full",
        sslrootcert="/etc/ssl/rds ca.pem",
        connect_timeout=2,
    )


@pytest.mark.parametrize(
    "query",
    [
        "connect_timeout=5",
        "sslmode=verify-full&sslmode=require",
        "host=attacker.example",
        "user=autoshop_owner",
    ],
)
def test_psycopg2_connection_arguments_reject_unapproved_url_query_parameters(query):
    from src.scripts.run_migrations import _psycopg2_connection_arguments

    database_url = (
        "postgresql+psycopg2://autoshop_migrations_hml:test-password@"
        "db.example.us-east-1.rds.amazonaws.com:5432/autoshop_hml?" + query
    )

    with pytest.raises(RuntimeError, match="configuration is invalid"):
        _psycopg2_connection_arguments(database_url)


def test_migration_database_url_uses_the_scoped_migration_secret(monkeypatch):
    monkeypatch.setenv(
        "MIGRATION_DATABASE_SECRET_ARN",
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:auto-shop/staging/hml/migrations-AbCdEf",
    )
    monkeypatch.setenv("MIGRATION_DATABASE_NAME", "autoshop_hml")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    response = {
        "SecretString": json.dumps(
            {
                "username": "autoshop_migrations_hml",
                "password": "test-password:/%?#",
                "host": "db.example.us-east-1.rds.amazonaws.com",
                "port": "5432",
                "DATABASE_URL": "postgresql://owner:must-not-be-used@example/db",
            }
        )
    }

    with patch("src.scripts.run_migrations.boto3.client") as boto_client:
        boto_client.return_value.get_secret_value.return_value = response
        database_url = _load_migration_database_url()

    parsed_url = make_url(database_url)
    assert parsed_url.username == "autoshop_migrations_hml"
    assert parsed_url.password == "test-password:/%?#"
    assert parsed_url.host == "db.example.us-east-1.rds.amazonaws.com"
    assert parsed_url.database == "autoshop_hml"
    assert parsed_url.query["sslmode"] == "verify-full"
    assert Path(parsed_url.query["sslrootcert"]).name == "rds-us-east-1-bundle.pem"
    assert "owner" not in parsed_url.username
    boto_client.assert_called_once_with("secretsmanager", region_name="us-east-1")
    boto_client.return_value.get_secret_value.assert_called_once_with(
        SecretId="arn:aws:secretsmanager:us-east-1:123456789012:secret:auto-shop/staging/hml/migrations-AbCdEf"
    )


def test_migration_database_url_rejects_a_secret_with_the_wrong_database_role(
    monkeypatch,
):
    monkeypatch.setenv(
        "MIGRATION_DATABASE_SECRET_ARN",
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:auto-shop/staging/hml/migrations-AbCdEf",
    )
    monkeypatch.setenv("MIGRATION_DATABASE_NAME", "autoshop_hml")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    with patch("src.scripts.run_migrations.boto3.client") as boto_client:
        boto_client.return_value.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "username": "autoshop_owner",
                    "password": "test-password",
                    "host": "db.example.us-east-1.rds.amazonaws.com",
                    "port": "5432",
                }
            )
        }
        with pytest.raises(RuntimeError, match="credentials are invalid"):
            _load_migration_database_url()


@pytest.mark.parametrize("app_env", ["staging", "production", "prod"])
def test_deployed_migration_config_fails_closed_without_migration_secret(
    monkeypatch, app_env
):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.delenv("MIGRATION_DATABASE_SECRET_ARN", raising=False)

    with pytest.raises(RuntimeError, match="configuration is incomplete"):
        _migration_config()


def test_run_migrations_returns_database_unavailable_code_without_logging_connection_details():
    with (
        patch(
            "src.scripts.run_migrations._migration_config",
            return_value=(
                "postgresql+psycopg2://user:password@localhost:5432/testdb",
                5,
                False,
            ),
        ),
        patch(
            "src.scripts.run_migrations.psycopg2.connect",
            side_effect=psycopg2.OperationalError("connection refused"),
        ),
        patch("src.scripts.run_migrations.subprocess.run") as run,
    ):
        assert run_migrations() == 10

    run.assert_not_called()


def test_run_migrations_logs_retryable_database_connection_failure_without_secrets(
    capsys,
):
    secret = "must-not-appear-in-logs"
    error = psycopg2.OperationalError(
        f"connection to db.internal failed: connection refused; password={secret}"
    )

    with (
        patch(
            "src.scripts.run_migrations._migration_config",
            return_value=("postgresql://user:password@db.internal/testdb", 2, False),
        ),
        patch("src.scripts.run_migrations.psycopg2.connect", side_effect=error),
    ):
        assert run_migrations() == 10

    output = capsys.readouterr().err
    assert "connection was refused" in output
    assert "retryable=true" in output
    assert secret not in output
    assert "db.internal" not in output


def test_run_migrations_does_not_retry_invalid_database_configuration(capsys):
    with (
        patch(
            "src.scripts.run_migrations._migration_config",
            return_value=("sqlite://", 2, False),
        ),
        patch("src.scripts.run_migrations.psycopg2.connect") as connect,
    ):
        assert run_migrations() == 20

    connect.assert_not_called()
    assert "invalid database configuration" in capsys.readouterr().err


def test_run_migrations_fails_immediately_when_another_migration_holds_the_lock(capsys):
    connection = FakeConnection()
    connection.cursor_instance.fetchone.return_value = (False,)

    with (
        patch(
            "src.scripts.run_migrations._migration_config",
            return_value=(
                "postgresql+psycopg2://user:password@localhost:5432/testdb",
                5,
                False,
            ),
        ),
        patch("src.scripts.run_migrations.psycopg2.connect", return_value=connection),
        patch("src.scripts.run_migrations.subprocess.run") as run,
    ):
        assert run_migrations() == 20

    run.assert_not_called()
    assert "another migration is already holding" in capsys.readouterr().err


def test_run_migrations_propagates_alembic_failure_code():
    connection = FakeConnection()

    with (
        patch(
            "src.scripts.run_migrations._migration_config",
            return_value=(
                "postgresql+psycopg2://user:password@localhost:5432/testdb",
                5,
                False,
            ),
        ),
        patch("src.scripts.run_migrations.psycopg2.connect", return_value=connection),
        patch(
            "src.scripts.run_migrations.subprocess.run",
            return_value=Mock(returncode=3),
        ),
    ):
        assert run_migrations() == 3
