import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / ".."
    / "alembic"
    / "versions"
    / "017_customer_access_status.py"
).resolve()


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_017", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_postgresql_migration_reuses_the_created_enum_type_for_the_column():
    dialect = type("Dialect", (), {"name": "postgresql"})()
    column_type = _load_migration()._column_type(type("Bind", (), {"dialect": dialect})())

    assert isinstance(column_type, postgresql.ENUM)
    assert column_type.name == "customerstatus"
    assert tuple(column_type.enums) == ("Ativo", "Inativo")
    assert column_type.create_type is False


def test_customer_status_migration_backfills_legacy_rows_and_can_rollback():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE customers ("
                "id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, "
                "email VARCHAR(255) NOT NULL, address VARCHAR(500) NOT NULL)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO customers (id, name, email, address) "
                "VALUES (1, 'Ana', 'ana@example.test', 'Rua A')"
            )
        )

        with Operations.context(MigrationContext.configure(connection)):
            _load_migration().upgrade()

        row = connection.execute(
            sa.text("SELECT id, name, email, address, status FROM customers WHERE id = 1")
        ).one()
        assert tuple(row) == (1, "Ana", "ana@example.test", "Rua A", "Ativo")

        status_column = next(
            column
            for column in sa.inspect(connection).get_columns("customers")
            if column["name"] == "status"
        )
        assert status_column["nullable"] is False
        assert "Ativo" in status_column["default"]

        with Operations.context(MigrationContext.configure(connection)):
            _load_migration().downgrade()

        assert "status" not in {
            column["name"] for column in sa.inspect(connection).get_columns("customers")
        }

    engine.dispose()
