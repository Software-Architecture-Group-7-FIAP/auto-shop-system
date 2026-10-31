from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "assert_no_active_lifecycle_runs.py"
SPEC = importlib.util.spec_from_file_location("assert_no_active_lifecycle_runs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT_GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT_GUARD)


def test_audit_guard_accepts_a_session_with_no_active_remote_mutations(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def list_runs(
        repository: str,
        _ref: str,
        _created_after: datetime,
        *,
        token: str,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        assert token == "token"
        assert timeout_seconds > 0
        calls.append((repository, _ref))
        return [
            {"display_title": "hml-2026-10-28-unrelated", "status": "in_progress"},
            {"display_title": "database/hml-2026-10-29/apply/bootstrap:old", "status": "completed"},
        ]

    monkeypatch.setattr(AUDIT_GUARD, "_list_repository_runs", list_runs)

    AUDIT_GUARD.assert_no_active_session_runs(
        token="token",
        app_repository="example/app",
        app_ref="develop",
        k8s_repository="example/k8s",
        k8s_ref="main",
        database_repository="example/database",
        database_ref="main",
        session_id="hml-2026-10-29",
        session_mode="hml",
        started_at="2026-10-29T12:00:00Z",
    )

    assert calls == [
        ("example/app", "develop"),
        ("example/k8s", "main"),
        ("example/database", "main"),
    ]


def test_audit_guard_fails_closed_when_a_matching_remote_run_is_active(monkeypatch: pytest.MonkeyPatch) -> None:
    def list_runs(
        repository: str,
        _ref: str,
        _created_after: datetime,
        *,
        token: str,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        assert token == "token"
        assert timeout_seconds > 0
        if repository == "example/database":
            return [
                {
                    "id": 1234,
                    "display_title": "database/prd-2026-11-01/teardown/destroy:dispatch-id",
                    "status": "canceling",
                }
            ]
        return []

    monkeypatch.setattr(AUDIT_GUARD, "_list_repository_runs", list_runs)

    with pytest.raises(AUDIT_GUARD.ActiveLifecycleRunError, match="database.*1234"):
        AUDIT_GUARD.assert_no_active_session_runs(
            token="token",
            app_repository="example/app",
            app_ref="main",
            k8s_repository="example/k8s",
            k8s_ref="main",
            database_repository="example/database",
            database_ref="main",
            session_id="prd-2026-11-01",
            session_mode="prd-window",
            started_at="2026-11-01T09:00:00Z",
        )


def test_audit_guard_waits_for_a_matching_teardown_to_finish(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 0.0
    database_polls = 0

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    def list_runs(
        repository: str,
        _ref: str,
        _created_after: datetime,
        *,
        token: str,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        nonlocal database_polls
        assert token == "token"
        assert timeout_seconds > 0
        if repository != "example/database":
            return []
        database_polls += 1
        if database_polls == 1:
            return [
                {
                    "id": 1234,
                    "display_title": "database/hml-2026-10-29/teardown/destroy:dispatch-id",
                    "status": "in_progress",
                }
            ]
        return []

    monkeypatch.setattr(AUDIT_GUARD, "_list_repository_runs", list_runs)
    monkeypatch.setattr(AUDIT_GUARD.time, "monotonic", monotonic)
    monkeypatch.setattr(AUDIT_GUARD.time, "sleep", sleep)

    AUDIT_GUARD.assert_no_active_session_runs(
        token="token",
        app_repository="example/app",
        app_ref="develop",
        k8s_repository="example/k8s",
        k8s_ref="main",
        database_repository="example/database",
        database_ref="main",
        session_id="hml-2026-10-29",
        session_mode="hml",
        started_at="2026-10-29T12:00:00Z",
        wait_seconds=30,
        poll_seconds=10,
    )

    assert database_polls == 2
    assert now == 10


def test_audit_guard_stops_waiting_at_its_finite_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 0.0
    database_polls = 0

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    def list_runs(
        repository: str,
        _ref: str,
        _created_after: datetime,
        *,
        token: str,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        nonlocal database_polls
        assert token == "token"
        assert timeout_seconds > 0
        if repository == "example/database":
            database_polls += 1
            return [
                {
                    "id": 1234,
                    "display_title": "database/hml-2026-10-29/teardown/destroy:dispatch-id",
                    "status": "in_progress",
                }
            ]
        return []

    monkeypatch.setattr(AUDIT_GUARD, "_list_repository_runs", list_runs)
    monkeypatch.setattr(AUDIT_GUARD.time, "monotonic", monotonic)
    monkeypatch.setattr(AUDIT_GUARD.time, "sleep", sleep)

    with pytest.raises(AUDIT_GUARD.ActiveLifecycleRunError, match="database.*1234.*after waiting 20 seconds"):
        AUDIT_GUARD.assert_no_active_session_runs(
            token="token",
            app_repository="example/app",
            app_ref="develop",
            k8s_repository="example/k8s",
            k8s_ref="main",
            database_repository="example/database",
            database_ref="main",
            session_id="hml-2026-10-29",
            session_mode="hml",
            started_at="2026-10-29T12:00:00Z",
            wait_seconds=20,
            poll_seconds=10,
        )

    assert database_polls == 2
    assert now == 20


def test_audit_guard_retries_temporary_api_errors_within_the_wait_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 0.0
    calls = 0

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    def list_runs(
        _repository: str,
        _ref: str,
        _created_after: datetime,
        *,
        token: str,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        nonlocal calls
        assert token == "token"
        assert timeout_seconds > 0
        calls += 1
        if calls == 1:
            raise AUDIT_GUARD.cross_repo_lifecycle.LifecycleDispatchError("temporary API failure")
        return []

    monkeypatch.setattr(AUDIT_GUARD, "_list_repository_runs", list_runs)
    monkeypatch.setattr(AUDIT_GUARD.time, "monotonic", monotonic)
    monkeypatch.setattr(AUDIT_GUARD.time, "sleep", sleep)

    AUDIT_GUARD.assert_no_active_session_runs(
        token="token",
        app_repository="example/app",
        app_ref="develop",
        k8s_repository="example/k8s",
        k8s_ref="main",
        database_repository="example/database",
        database_ref="main",
        session_id="hml-2026-10-29",
        session_mode="hml",
        started_at="2026-10-29T12:00:00Z",
        wait_seconds=30,
        poll_seconds=10,
    )

    assert calls == 4
    assert now == 10


def test_audit_guard_caps_api_timeout_to_the_remaining_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 0.0
    timeouts: list[float] = []

    def monotonic() -> float:
        return now

    def list_runs(
        _repository: str,
        _ref: str,
        _created_after: datetime,
        *,
        token: str,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        nonlocal now
        assert token == "token"
        timeouts.append(timeout_seconds)
        now += timeout_seconds
        raise AUDIT_GUARD.cross_repo_lifecycle.LifecycleDispatchError("API request timed out")

    monkeypatch.setattr(AUDIT_GUARD, "_list_repository_runs", list_runs)
    monkeypatch.setattr(AUDIT_GUARD.time, "monotonic", monotonic)

    with pytest.raises(AUDIT_GUARD.ActiveLifecycleRunError, match="could not be queried"):
        AUDIT_GUARD.assert_no_active_session_runs(
            token="token",
            app_repository="example/app",
            app_ref="develop",
            k8s_repository="example/k8s",
            k8s_ref="main",
            database_repository="example/database",
            database_ref="main",
            session_id="hml-2026-10-29",
            session_mode="hml",
            started_at="2026-10-29T12:00:00Z",
            wait_seconds=10,
            poll_seconds=2,
        )

    assert timeouts == [10]
    assert now == 10
