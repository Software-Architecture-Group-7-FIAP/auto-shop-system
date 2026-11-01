import importlib.util
from contextlib import redirect_stderr
from datetime import datetime, timezone
from io import StringIO
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
            return datetime(2026, 10, 31, 17, 30, tzinfo=timezone.utc)

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


def test_hml_open_accepts_the_approved_november_5_cutoff(monkeypatch, tmp_path) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 5, 12, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(SESSION, "datetime", FrozenDateTime)
    output = tmp_path / "github-output"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT),
            "--action",
            "start",
            "--stage",
            "hml",
            "--started-at",
            "2026-11-05T12:00:00Z",
            "--session-mode",
            "hml",
            "--github-output",
            str(output),
        ],
    )

    assert SESSION.main() == 0
    assert "session_id=hml-2026-11-05" in output.read_text(encoding="utf-8")


def test_hml_open_rejects_the_day_after_the_approved_cutoff(monkeypatch, tmp_path) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 6, 12, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(SESSION, "datetime", FrozenDateTime)
    output = tmp_path / "github-output"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT),
            "--action",
            "start",
            "--stage",
            "hml",
            "--started-at",
            "2026-11-06T12:00:00Z",
            "--session-mode",
            "hml",
            "--github-output",
            str(output),
        ],
    )
    stderr = StringIO()

    with redirect_stderr(stderr):
        assert SESSION.main() == 1

    assert "through 5 November 2026 BRT" in stderr.getvalue()
    assert not output.exists()
