from unittest.mock import Mock, patch

import psycopg2

from src.scripts.run_migrations import MIGRATION_LOCK_KEY, run_migrations


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
