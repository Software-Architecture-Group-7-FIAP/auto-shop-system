import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".github" / "scripts" / "dispatch_expired_lifecycle_sessions.py"
SPEC = importlib.util.spec_from_file_location("dispatch_expired_lifecycle_sessions", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
DISPATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DISPATCHER)


def _session(stage: str = "hml", scope: str = "infrastructure-only") -> dict[str, str]:
    return {
        "session_id": f"{stage}-2026-10-31",
        "stage": stage,
        "started_at": "2026-10-31T13:00:00Z",
        "session_mode": "hml" if stage == "hml" else "prd-window",
        "session_scope": scope,
        "status": "active",
    }


def test_cleanup_accepts_only_infrastructure_only_hml_sessions() -> None:
    assert DISPATCHER._validate_session(_session()) == (
        "hml-2026-10-31",
        "hml",
        "2026-10-31T13:00:00Z",
        "hml",
    )
    assert DISPATCHER._validate_session(_session(stage="prd", scope="integrated")) is None
    assert DISPATCHER._validate_session(_session(scope="integrated")) is None


def test_cleanup_rejects_malformed_hml_session() -> None:
    invalid = _session()
    invalid["session_id"] = "hml-2026-10-30"

    with pytest.raises(ValueError, match="outside its session date"):
        DISPATCHER._validate_session(invalid)
