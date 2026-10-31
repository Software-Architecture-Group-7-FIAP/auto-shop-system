import importlib.util
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "resolve_lifecycle_session.py"
SPEC = importlib.util.spec_from_file_location("resolve_lifecycle_session", SCRIPT)
SESSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SESSION)


def test_hml_teardown_accepts_the_resolved_session_mode(monkeypatch, tmp_path) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 31, 16, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(SESSION, "datetime", FrozenDateTime)
    output = tmp_path / "github-output"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT),
            "--action",
            "teardown",
            "--stage",
            "hml",
            "--session-id",
            "hml-2026-10-31",
            "--started-at",
            "2026-10-31T12:00:00Z",
            "--session-mode",
            "hml",
            "--github-output",
            str(output),
        ],
    )

    assert SESSION.main() == 0
    assert "session_mode=hml" in output.read_text(encoding="utf-8")
