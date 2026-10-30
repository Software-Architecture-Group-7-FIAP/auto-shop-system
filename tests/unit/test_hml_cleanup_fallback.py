from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load_script(name: str):
    script = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CLEANUP = _load_script("resolve_hml_cleanup_session")
RESOLVER = _load_script("resolve_lifecycle_session")
WINDOW = _load_script("validate_environment_window")
CLOSE_GUARD = _load_script("assert_lifecycle_close_needed")
AUTH = _load_script("lifecycle_session_auth")


def _opening(
    title: str,
    *,
    run_id: int = 101,
    created_at: str = "2026-10-30T20:00:00Z",
    branch: str = "main",
    event: str = "workflow_dispatch",
) -> dict[str, object]:
    return {
        "id": run_id,
        "display_title": title,
        "created_at": created_at,
        "head_branch": branch,
        "event": event,
    }


def _close(
    title: str,
    *,
    status: str = "completed",
    conclusion: str = "success",
) -> dict[str, object]:
    return {"display_title": title, "status": status, "conclusion": conclusion}


def test_default_hml_opening_resolves_to_the_default_brt_start() -> None:
    session = CLEANUP.parse_hml_opening_run(
        _opening("lifecycle:hml:open:default-17-BRT:101"), default_branch="main"
    )

    assert session.session_id == "hml-2026-10-30"
    assert session.started_at == "2026-10-30T20:00:00Z"
    assert session.run_id == 101


def test_explicit_hml_start_is_preserved_in_canonical_utc() -> None:
    session = CLEANUP.parse_hml_opening_run(
        _opening(
            "lifecycle:hml:open:2026-10-30T12:00:00Z:101",
            created_at="2026-10-30T12:05:00Z",
        ),
        default_branch="main",
    )

    assert session.session_id == "hml-2026-10-30"
    assert session.started_at == "2026-10-30T12:00:00Z"


@pytest.mark.parametrize(
    ("branch", "event"),
    [("develop", "workflow_dispatch"), ("main", "push")],
)
def test_only_default_branch_manual_hml_openings_are_candidates(branch: str, event: str) -> None:
    session = CLEANUP.parse_hml_opening_run(
        _opening("lifecycle:hml:open:default-17-BRT:101", branch=branch, event=event),
        default_branch="main",
    )

    assert session is None


def test_invalid_hml_opening_title_fails_closed() -> None:
    with pytest.raises(ValueError, match="malformed HML opening title"):
        CLEANUP.parse_hml_opening_run(
            _opening("lifecycle:hml:open:not-a-session:101"), default_branch="main"
        )


def test_opening_created_after_its_authorized_window_fails_closed() -> None:
    with pytest.raises(ValueError, match="created after its authorized session window"):
        CLEANUP.parse_hml_opening_run(
            _opening(
                "lifecycle:hml:open:default-17-BRT:101",
                created_at="2026-10-31T01:00:00Z",
            ),
            default_branch="main",
        )


def test_resolver_selects_one_mutating_hml_session_without_a_successful_or_active_close() -> None:
    session = CLEANUP.find_cleanup_candidate(
        [_opening("lifecycle:hml:open:default-17-BRT:101")],
        [_close("lifecycle:hml:close:hml-2026-10-30:auto-99:dispatch", conclusion="failure")],
        default_branch="main",
        now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
        mutation_started=lambda _run_id: True,
    )

    assert session.session_id == "hml-2026-10-30"


@pytest.mark.parametrize(
    "close_run",
    [
        _close("lifecycle:hml:close:hml-2026-10-30:auto-99:dispatch"),
        _close(
            "lifecycle:hml:close:hml-2026-10-30:auto-99:dispatch",
            status="in_progress",
            conclusion="",
        ),
        _close(
            "lifecycle:hml:close:hml-2026-10-30:auto-100:dispatch",
            status="canceling",
            conclusion="",
        ),
    ],
)
def test_successful_or_active_close_is_not_dispatched_again(close_run: dict[str, object]) -> None:
    session = CLEANUP.find_cleanup_candidate(
        [_opening("lifecycle:hml:open:default-17-BRT:101")],
        [close_run],
        default_branch="main",
        now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
        mutation_started=lambda _run_id: True,
    )

    assert session is None


def test_session_that_never_started_mutating_infrastructure_is_skipped() -> None:
    session = CLEANUP.find_cleanup_candidate(
        [_opening("lifecycle:hml:open:default-17-BRT:101")],
        [],
        default_branch="main",
        now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
        mutation_started=lambda _run_id: False,
    )

    assert session is None


def test_previous_opening_attempt_mutation_is_not_hidden_by_an_unmutated_rerun() -> None:
    marker = CLOSE_GUARD.FIRST_MUTATION_MARKER
    jobs = [
        {
            "name": "open",
            "conclusion": "failure",
            "steps": [{"name": marker, "started_at": "2026-10-30T20:05:00Z"}],
        },
        {
            "name": "open",
            "conclusion": "failure",
            "steps": [{"name": marker, "started_at": None}],
        },
    ]

    assert CLOSE_GUARD.has_started_mutating_job(jobs) is True


def test_multiple_unclosed_mutating_sessions_fail_closed() -> None:
    openings = [
        _opening("lifecycle:hml:open:default-17-BRT:101", run_id=101),
        _opening(
            "lifecycle:hml:open:2026-10-30T12:00:00Z:102",
            run_id=102,
            created_at="2026-10-30T12:30:00Z",
        ),
    ]

    with pytest.raises(ValueError, match="multiple unclosed HML sessions"):
        CLEANUP.find_cleanup_candidate(
            openings,
            [],
            default_branch="main",
            now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
            mutation_started=lambda _run_id: True,
        )


def test_emergency_resolver_allows_only_an_expired_hml_teardown_and_reserves_a_new_deadline() -> None:
    now = datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc)
    resolved = RESOLVER.resolve_emergency_hml_teardown(
        stage="hml",
        session_id="hml-2026-10-31",
        started_at="2026-10-31T20:00:00Z",
        now=now,
    )

    assert resolved["teardown_allowed"] is True
    assert datetime.strptime(resolved["teardown_deadline_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    ) == now + timedelta(minutes=40)
    assert datetime.strptime(resolved["cleanup_end_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    ) == now + timedelta(hours=1)


@pytest.mark.parametrize(
    ("stage", "session_id", "started_at"),
    [
        ("prd", "prd-2026-10-31", "2026-10-31T09:00:00Z"),
        ("hml", "hml-2026-11-01", "2026-11-01T20:00:00Z"),
        ("hml", "hml-2026-10-30", "2026-10-31T20:00:00Z"),
    ],
)
def test_emergency_resolver_rejects_wrong_stage_or_session_date(
    stage: str, session_id: str, started_at: str
) -> None:
    with pytest.raises(ValueError):
        RESOLVER.resolve_emergency_hml_teardown(
            stage=stage,
            session_id=session_id,
            started_at=started_at,
            now=datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc),
        )


def test_emergency_window_allows_old_hml_close_but_normal_close_remains_time_bounded() -> None:
    values = {
        "active": "false",
        "authorized": "false",
        "session_id": "hml-2026-10-31",
        "stage": "hml",
        "action": "teardown",
        "started_at": "2026-10-31T20:00:00Z",
        "now": datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc),
    }

    assert WINDOW.validate_environment_window(**values, emergency_hml_teardown=True) == timedelta(0)
    with pytest.raises(WINDOW.EnvironmentWindowError):
        WINDOW.validate_environment_window(**values)


def test_emergency_capability_is_purpose_and_request_bound() -> None:
    key = "test-signing-key-with-at-least-32-bytes"
    session_id = "hml-2026-10-31"
    started_at = "2026-10-31T20:00:00Z"
    request_id = "emergency-12345"
    regular_token = AUTH.sign_lifecycle_session(key, "hml", session_id, started_at)
    emergency_token = AUTH.sign_emergency_hml_cleanup(key, session_id, started_at, request_id)

    assert emergency_token != regular_token
    AUTH.verify_emergency_hml_cleanup(key, emergency_token, session_id, started_at, request_id)
    with pytest.raises(AUTH.LifecycleSessionAuthError):
        AUTH.verify_emergency_hml_cleanup(key, regular_token, session_id, started_at, request_id)
    with pytest.raises(AUTH.LifecycleSessionAuthError):
        AUTH.verify_emergency_hml_cleanup(key, emergency_token, session_id, started_at, "emergency-12346")


def test_fallback_workflow_is_hml_only_and_dispatches_the_existing_close_flow_to_develop() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-hml-cleanup.yml").read_text(
        encoding="utf-8"
    )

    assert 'cron: "0 2 * * *"' in workflow
    assert "environment-stop.yml --ref develop" in workflow
    assert '\\"stage\\":\\"hml\\"' in workflow
    assert '\\"emergency_cleanup\\":\\"true\\"' in workflow
    assert "close_needed" in workflow
    assert "LIFECYCLE_SESSION_SIGNING_KEY" in workflow
    assert "--emergency-hml-cleanup" in workflow
    assert "CLOSE_REQUEST_ID: emergency-${{ github.run_id }}" in workflow
    assert "id-token: write" not in workflow


def test_stop_workflow_requires_a_signed_hml_capability_for_emergency_cleanup() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-stop.yml").read_text(
        encoding="utf-8"
    )

    assert "emergency_cleanup" in workflow
    assert "--emergency-hml-teardown" in workflow
    assert '"$EMERGENCY_CLEANUP" == "true"' in workflow
    assert "CLOSE_REQUEST_ID: ${{ inputs.close_request_id }}" in workflow
