import importlib.util
from pathlib import Path

import pytest


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "010_public_token_hardening.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_010", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_token_hardening_downgrade_refuses_data_loss():
    with pytest.raises(RuntimeError, match="irreversible"):
        _load_migration().downgrade()
