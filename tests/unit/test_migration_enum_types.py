"""Guard the PostgreSQL enum handling in migration 011.

``create_type`` is a ``postgresql.ENUM`` argument. ``sa.Enum`` accepts and
silently discards it, and the adapted native type then emits a ``CREATE TYPE``
for a type migration 009 already created, aborting ``alembic upgrade head``
with ``DuplicateObject``.

Verified against postgres:16-alpine: upgrading a database already at 010 fails
with the pre-fix form and succeeds with this one. Note that building a database
from scratch in a single run does *not* reproduce it (alembic's DDL-runner memo
carries the type name over from migration 001), and SQLite -- where the rest of
the suite runs -- has no native enum at all. Hence this check.
"""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "011_auth_sessions_and_audit.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_011", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeBind:
    def __init__(self, name: str):
        self.dialect = type("Dialect", (), {"name": name})()


def _emits_create_type(type_) -> bool:
    metadata = sa.MetaData()
    sa.Table("probe", metadata, sa.Column("status", type_, nullable=False))
    emitted = []
    engine = sa.create_mock_engine(
        "postgresql://", lambda sql, *args, **kwargs: emitted.append(type(sql).__name__)
    )
    metadata.create_all(engine, checkfirst=False)
    return "CreateEnumType" in emitted


def test_status_enum_does_not_recreate_the_existing_postgres_type():
    migration = _load_migration()

    type_ = migration._existing_service_order_status_enum(_FakeBind("postgresql"))

    assert isinstance(type_, postgresql.ENUM)
    assert type_.create_type is False
    assert _emits_create_type(type_) is False


def test_status_enum_falls_back_to_a_portable_type_off_postgres():
    migration = _load_migration()

    type_ = migration._existing_service_order_status_enum(_FakeBind("sqlite"))

    assert isinstance(type_, sa.Enum)
    assert type_.name == "serviceorderstatus"


def test_sa_enum_would_have_recreated_the_type():
    """The shape this migration must not go back to."""
    unsafe = sa.Enum("Recebida", name="serviceorderstatus", create_type=False)

    assert unsafe.dialect_impl(postgresql.dialect()).create_type is True
    assert _emits_create_type(unsafe) is True
