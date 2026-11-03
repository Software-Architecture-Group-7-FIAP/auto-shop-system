from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "validate_environment_window.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("validate_environment_window", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
WINDOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WINDOW)


def test_hml_deploy_authorization_is_not_limited_to_the_session_hours() -> None:
    WINDOW.validate_environment_window(
        active="true",
        authorized="true",
        session_id="hml-2026-11-01",
        stage="hml",
        action="deploy",
        started_at="2026-11-01T10:00:00Z",
        now=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc),
    )


def test_prd_deploy_authorization_is_not_limited_to_the_lifecycle_hours() -> None:
    WINDOW.validate_environment_window(
        active="true",
        authorized="true",
        session_id="prd-2026-11-01",
        stage="prd",
        action="deploy",
        started_at="2026-11-01T09:00:00Z",
        now=datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc),
    )


def test_deploy_authorization_still_requires_an_active_authorized_environment() -> None:
    try:
        WINDOW.validate_environment_window(
            active="true",
            authorized="false",
            session_id="hml-2026-11-01",
            stage="hml",
            action="deploy",
            started_at="2026-11-01T10:00:00Z",
            now=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc),
        )
    except WINDOW.EnvironmentWindowError as error:
        assert "authorized" in str(error)
    else:
        raise AssertionError("deploy authorization must preserve the static authorization gates")
