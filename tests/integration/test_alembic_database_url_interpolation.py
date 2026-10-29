from pathlib import Path

from alembic import command
from alembic.config import Config

from src.config import settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_offline_upgrade_preserves_percent_encoded_database_password(monkeypatch):
    database_url = "postgresql://oficina:p%25ss%40word@localhost:5432/oficina"
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))

    command.upgrade(config, "002", sql=True)

    assert config.get_main_option("sqlalchemy.url") == database_url
