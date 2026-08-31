from sqlalchemy.exc import OperationalError

from src.infrastructure import database


class FakeConnection:
    def __init__(self, error=None):
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement):
        if self.error:
            raise self.error
        return None


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        return self.connection


def test_check_database_connection_returns_true_after_select_one(monkeypatch):
    monkeypatch.setattr(database, "engine", FakeEngine(FakeConnection()))

    assert database.check_database_connection() is True


def test_check_database_connection_returns_false_without_exposing_database_error(monkeypatch):
    error = OperationalError("SELECT 1", {}, Exception("connection refused"))
    monkeypatch.setattr(database, "engine", FakeEngine(FakeConnection(error)))

    assert database.check_database_connection() is False
