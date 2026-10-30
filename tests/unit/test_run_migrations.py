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
        patch("src.scripts.run_migrations.psycopg2.connect", return_value=connection),
        patch("src.scripts.run_migrations.subprocess.run", return_value=completed) as run,
    ):
        assert run_migrations() == 0

    connection.cursor_instance.execute.assert_called_once_with(
        "SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,)
    )
    run.assert_called_once_with(["alembic", "upgrade", "head"], check=False)


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


def test_migration_database_url_rejects_a_secret_with_the_wrong_database_role(monkeypatch):
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
    with patch(
        "src.scripts.run_migrations.psycopg2.connect",
        side_effect=psycopg2.OperationalError("connection refused"),
    ), patch("src.scripts.run_migrations.subprocess.run") as run:
        assert run_migrations() == 10

    run.assert_not_called()


def test_run_migrations_propagates_alembic_failure_code():
    connection = FakeConnection()

    with (
        patch("src.scripts.run_migrations.psycopg2.connect", return_value=connection),
        patch(
            "src.scripts.run_migrations.subprocess.run",
            return_value=Mock(returncode=3),
        ),
    ):
        assert run_migrations() == 3
