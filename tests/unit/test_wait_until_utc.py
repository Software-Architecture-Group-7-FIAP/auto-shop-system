from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "wait_until_utc.py"
SPEC = importlib.util.spec_from_file_location("wait_until_utc", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
WAIT_UNTIL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WAIT_UNTIL)


def test_waits_until_target_in_bounded_intervals(monkeypatch: pytest.MonkeyPatch) -> None:
    current = datetime(2026, 10, 29, 22, 0, tzinfo=timezone.utc)
    sleeps: list[float] = []

    def now() -> datetime:
        return current

    def sleep(seconds: float) -> None:
        nonlocal current
        sleeps.append(seconds)
        current += timedelta(seconds=seconds)

    monkeypatch.setattr(WAIT_UNTIL, "_utc_now", now)
    monkeypatch.setattr(WAIT_UNTIL.time, "sleep", sleep)

    WAIT_UNTIL.wait_until_utc(
        "2026-10-29T22:01:10Z",
        "2026-10-29T22:15:00Z",
    )

    assert sleeps == [30, 30, 10]
    assert current == datetime(2026, 10, 29, 22, 1, 10, tzinfo=timezone.utc)


def test_rejects_target_after_cleanup_deadline() -> None:
    with pytest.raises(WAIT_UNTIL.AuditDeadlineError, match="must be before the cleanup deadline"):
        WAIT_UNTIL.wait_until_utc("2026-10-29T22:15:00Z", "2026-10-29T22:15:00Z")
