from __future__ import annotations

import importlib.util
import json
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
OPERATOR_AUTH = _load_script("authorize_hml_cleanup")


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
    retry_safe: bool | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {"display_title": title, "status": status, "conclusion": conclusion}
    if retry_safe is not None:
        value["retry_safe"] = retry_safe
    return value


def _safe_close_jobs(*, mutation_started: bool = False) -> list[dict[str, object]]:
    markers = [
        {"name": name, "started_at": "2026-10-30T20:10:00Z" if mutation_started and index == 0 else None}
        for index, name in enumerate(CLOSE_GUARD.CLOSE_MUTATION_MARKERS)
    ]
    return [{"name": "close", "status": "completed", "conclusion": "failure", "steps": markers}]


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


def test_resolver_only_retries_a_failed_close_when_job_evidence_proves_no_mutation_started() -> None:
    session = CLEANUP.find_cleanup_candidate(
        [_opening("lifecycle:hml:open:default-17-BRT:101")],
        [_close(
            "lifecycle:hml:close:hml-2026-10-30:auto-99:dispatch",
            conclusion="failure",
            retry_safe=True,
        )],
        default_branch="main",
        now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
        mutation_accepted=lambda _session, _opening: True,
        close_retry_safe=lambda run: run.get("retry_safe") is True,
    )

    assert session.session_id == "hml-2026-10-30"


def test_resolver_fails_closed_for_failed_close_without_retry_evidence() -> None:
    with pytest.raises(ValueError, match="operator phase review is required"):
        CLEANUP.find_cleanup_candidate(
            [_opening("lifecycle:hml:open:default-17-BRT:101")],
            [_close("lifecycle:hml:close:hml-2026-10-30:auto-99:dispatch", conclusion="failure")],
            default_branch="main",
            now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
            mutation_accepted=lambda _session, _opening: True,
            close_retry_safe=lambda run: run.get("retry_safe") is True,
        )


def test_resolver_does_not_retry_after_any_close_mutation_phase_started() -> None:
    assert CLOSE_GUARD.close_run_proves_no_mutation(_safe_close_jobs()) is True
    assert CLOSE_GUARD.close_run_proves_no_mutation(_safe_close_jobs(mutation_started=True)) is False

    with pytest.raises(ValueError, match="operator phase review is required"):
        CLEANUP.find_cleanup_candidate(
            [_opening("lifecycle:hml:open:default-17-BRT:101")],
            [_close(
                "lifecycle:hml:close:hml-2026-10-30:auto-99:dispatch",
                conclusion="failure",
                retry_safe=False,
            )],
            default_branch="main",
            now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
            mutation_accepted=lambda _session, _opening: True,
            close_retry_safe=lambda run: run.get("retry_safe") is True,
        )


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
    if close_run.get("status") in CLEANUP.ACTIVE_STATUSES:
        with pytest.raises(ValueError, match="still active"):
            CLEANUP.find_cleanup_candidate(
                [_opening("lifecycle:hml:open:default-17-BRT:101")],
                [close_run],
                default_branch="main",
                now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
                mutation_accepted=lambda _session, _opening: True,
                close_retry_safe=lambda run: run.get("retry_safe") is True,
            )
    else:
        session = CLEANUP.find_cleanup_candidate(
            [_opening("lifecycle:hml:open:default-17-BRT:101")],
            [close_run],
            default_branch="main",
            now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
            mutation_accepted=lambda _session, _opening: True,
            close_retry_safe=lambda run: run.get("retry_safe") is True,
        )
        assert session is None


def test_upstream_foundation_apply_acceptance_requires_exact_correlated_run() -> None:
    started_after = datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc)
    title = "hml-2026-10-30-foundation-open-apply:" + "a" * 32
    accepted_run = {
        "id": 501,
        "display_title": title,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "status": "completed",
        "conclusion": "failure",
        "created_at": "2026-10-30T20:01:00Z",
    }
    started_jobs = [{
        "name": "apply reviewed saved plan",
        "status": "completed",
        "conclusion": "failure",
        "steps": [{
            "name": "Verify and apply the exact saved plan",
            "started_at": "2026-10-30T20:02:00Z",
            "conclusion": "failure",
        }],
    }]

    assert CLEANUP.has_accepted_opening_apply_run(
        [accepted_run],
        session_id="hml-2026-10-30",
        ref="main",
        started_after=started_after,
        jobs_for_run=lambda _run_id: started_jobs,
    ) is True
    assert CLEANUP.has_accepted_opening_apply_run(
        [{**accepted_run, "display_title": "unrelated:" + "a" * 32}],
        session_id="hml-2026-10-30",
        ref="main",
        started_after=started_after,
        jobs_for_run=lambda _run_id: started_jobs,
    ) is False
    assert CLEANUP.has_accepted_opening_apply_run(
        [{**accepted_run, "head_branch": "develop"}],
        session_id="hml-2026-10-30",
        ref="main",
        started_after=started_after,
        jobs_for_run=lambda _run_id: started_jobs,
    ) is False
    assert CLEANUP.has_accepted_opening_apply_run(
        [{**accepted_run, "created_at": "2026-10-30T19:59:00Z"}],
        session_id="hml-2026-10-30",
        ref="main",
        started_after=started_after,
        jobs_for_run=lambda _run_id: started_jobs,
    ) is False


def test_upstream_apply_run_without_a_started_scoped_step_is_not_accepted() -> None:
    run = {
        "id": 502,
        "display_title": "hml-2026-10-30-foundation-open-apply:" + "b" * 32,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "status": "completed",
        "conclusion": "skipped",
        "created_at": "2026-10-30T20:01:00Z",
    }
    skipped_job = [{
        "name": "apply reviewed saved plan",
        "status": "completed",
        "conclusion": "skipped",
        "steps": [],
    }]

    assert CLEANUP.has_accepted_opening_apply_run(
        [run],
        session_id="hml-2026-10-30",
        ref="main",
        started_after=datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc),
        jobs_for_run=lambda _run_id: skipped_job,
    ) is False


def test_upstream_apply_fails_closed_when_the_scoped_step_evidence_is_missing() -> None:
    run = {
        "id": 503,
        "display_title": "hml-2026-10-30-foundation-open-apply:" + "c" * 32,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "status": "completed",
        "conclusion": "failure",
        "created_at": "2026-10-30T20:01:00Z",
    }

    with pytest.raises(ValueError, match="expected opening apply job"):
        CLEANUP.has_accepted_opening_apply_run(
            [run],
            session_id="hml-2026-10-30",
            ref="main",
            started_after=datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc),
            jobs_for_run=lambda _run_id: [{"name": "unexpected"}],
        )
    with pytest.raises(ValueError, match="step evidence is missing or ambiguous"):
        CLEANUP.has_accepted_opening_apply_run(
            [run],
            session_id="hml-2026-10-30",
            ref="main",
            started_after=datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc),
            jobs_for_run=lambda _run_id: [{
                "name": "apply reviewed saved plan",
                "status": "completed",
                "conclusion": "failure",
                "steps": [],
            }],
        )


def test_workflow_run_pagination_fails_closed_on_incomplete_pages(monkeypatch) -> None:
    responses = iter([
        {"total_count": 2, "workflow_runs": [{"id": 1}]},
        {"total_count": 2, "workflow_runs": []},
    ])
    monkeypatch.setattr(CLEANUP, "_api_request", lambda *_args: next(responses))

    with pytest.raises(ValueError, match="incomplete apply.yml run listing"):
        CLEANUP._workflow_runs("owner/infra", "apply.yml", "token")


def test_workflow_run_pagination_rejects_duplicate_ids(monkeypatch) -> None:
    responses = iter([
        {"total_count": 2, "workflow_runs": [{"id": 1}]},
        {"total_count": 2, "workflow_runs": [{"id": 1}]},
    ])
    monkeypatch.setattr(CLEANUP, "_api_request", lambda *_args: next(responses))

    with pytest.raises(ValueError, match="duplicate apply.yml run IDs"):
        CLEANUP._workflow_runs("owner/infra", "apply.yml", "token")


def test_workflow_job_lookup_includes_all_rerun_attempts_and_requires_complete_pagination(monkeypatch) -> None:
    responses = iter([
        {"total_count": 2, "jobs": [{"id": 11}]},
        {"total_count": 2, "jobs": [{"id": 12}]},
    ])
    paths: list[str] = []

    def respond(_token: str, path: str):
        paths.append(path)
        return next(responses)

    monkeypatch.setattr(CLEANUP, "_api_request", respond)

    jobs = CLEANUP._workflow_jobs("owner/infra", 501, "token")

    assert jobs == [{"id": 11}, {"id": 12}]
    assert len(paths) == 2
    assert all("filter=all" in path for path in paths)


def test_workflow_job_pagination_rejects_duplicate_job_ids(monkeypatch) -> None:
    responses = iter([
        {"total_count": 2, "jobs": [{"id": 11}]},
        {"total_count": 2, "jobs": [{"id": 11}]},
    ])
    monkeypatch.setattr(CLEANUP, "_api_request", lambda *_args: next(responses))

    with pytest.raises(ValueError, match="duplicate upstream apply job IDs"):
        CLEANUP._workflow_jobs("owner/infra", 501, "token")


def test_close_guard_run_pagination_fails_closed_on_incomplete_pages(monkeypatch) -> None:
    responses = iter([
        {"total_count": 2, "workflow_runs": [{"id": 1}]},
        {"total_count": 2, "workflow_runs": []},
    ])

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(next(responses)).encode("utf-8")

    monkeypatch.setattr(CLOSE_GUARD, "urlopen", lambda *_args, **_kwargs: Response())

    with pytest.raises(ValueError, match="incomplete environment-stop.yml run listing"):
        CLOSE_GUARD._runs("owner/app", "environment-stop.yml", date(2026, 10, 30), "token")


def test_close_guard_run_pagination_rejects_duplicate_ids(monkeypatch) -> None:
    responses = iter([
        {"total_count": 2, "workflow_runs": [{"id": 1}]},
        {"total_count": 2, "workflow_runs": [{"id": 1}]},
    ])

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(next(responses)).encode("utf-8")

    monkeypatch.setattr(CLOSE_GUARD, "urlopen", lambda *_args, **_kwargs: Response())

    with pytest.raises(ValueError, match="duplicate environment-stop.yml run IDs"):
        CLOSE_GUARD._runs("owner/app", "environment-stop.yml", date(2026, 10, 30), "token")


def test_active_upstream_apply_blocks_emergency_cleanup() -> None:
    with pytest.raises(ValueError, match="upstream opening apply is still active"):
        CLEANUP.has_accepted_opening_apply_run(
            [{
                "display_title": "hml-2026-10-30-foundation-open-apply:" + "b" * 32,
                "event": "workflow_dispatch",
                "head_branch": "main",
                "status": "in_progress",
                "created_at": "2026-10-30T20:01:00Z",
            }],
            session_id="hml-2026-10-30",
            ref="main",
            started_after=datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc),
            jobs_for_run=lambda _run_id: [],
        )


def test_fallback_requires_local_apply_dispatch_marker_and_accepted_upstream_run(monkeypatch) -> None:
    opening = _opening("lifecycle:hml:open:default-17-BRT:101")
    session = CLEANUP.parse_hml_opening_run(opening, default_branch="main")
    assert session is not None
    monkeypatch.setattr(CLEANUP, "_opening_mutation_started", lambda *_args: True)
    monkeypatch.setattr(CLEANUP, "_workflow_runs", lambda *_args, **_kwargs: [])

    assert CLEANUP._opening_apply_was_accepted(
        session,
        opening,
        coordinator_repository="owner/app",
        infrastructure_repository="owner/infra",
        ref="main",
        token="test-token",
    ) is False

    accepted_run = {
        "id": 501,
        "display_title": "hml-2026-10-30-foundation-open-apply:" + "c" * 32,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "status": "completed",
        "conclusion": "failure",
        "created_at": "2026-10-30T20:01:00Z",
    }
    monkeypatch.setattr(CLEANUP, "_workflow_runs", lambda *_args, **_kwargs: [accepted_run])
    monkeypatch.setattr(CLEANUP, "_workflow_jobs", lambda *_args, **_kwargs: [{
        "name": "apply reviewed saved plan",
        "status": "completed",
        "conclusion": "failure",
        "steps": [{
            "name": "Verify and apply the exact saved plan",
            "started_at": "2026-10-30T20:02:00Z",
        }],
    }])
    assert CLEANUP._opening_apply_was_accepted(
        session,
        opening,
        coordinator_repository="owner/app",
        infrastructure_repository="owner/infra",
        ref="main",
        token="test-token",
    ) is True


def test_session_that_never_started_mutating_infrastructure_is_skipped() -> None:
    session = CLEANUP.find_cleanup_candidate(
        [_opening("lifecycle:hml:open:default-17-BRT:101")],
        [],
        default_branch="main",
        now=datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc),
        mutation_accepted=lambda _session, _opening: False,
        close_retry_safe=lambda run: run.get("retry_safe") is True,
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
            mutation_accepted=lambda _session, _opening: True,
            close_retry_safe=lambda run: run.get("retry_safe") is True,
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
    assert "authorize_hml_cleanup.py" in workflow
    assert "HML_CLEANUP_TRUSTED_OPERATORS" in workflow
    assert "REQUESTED_ACTOR: ${{ github.triggering_actor }}" in workflow
    assert "K8S_INFRA_REPOSITORY" in workflow
    assert workflow.index("authorize_hml_cleanup.py") < workflow.index("resolve_hml_cleanup_session.py")
    assert "environment: operations" in workflow


def test_stop_workflow_requires_a_signed_hml_capability_for_emergency_cleanup() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-stop.yml").read_text(
        encoding="utf-8"
    )

    assert "emergency_cleanup" in workflow
    assert "--emergency-hml-teardown" in workflow
    assert '"$EMERGENCY_CLEANUP" == "true"' in workflow
    assert "CLOSE_REQUEST_ID: ${{ inputs.close_request_id }}" in workflow
    assert 'REQUESTED_REF" == "develop"' in workflow
    assert "environment: operations" in workflow


def test_failed_close_retry_contract_tracks_every_potential_mutation_step() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-stop.yml").read_text(
        encoding="utf-8"
    )

    positions = [workflow.index(marker) for marker in CLOSE_GUARD.CLOSE_MUTATION_MARKERS]
    assert positions == sorted(positions)
    assert CLOSE_GUARD.close_run_proves_no_mutation(_safe_close_jobs()) is True
    assert CLOSE_GUARD.close_run_proves_no_mutation(_safe_close_jobs(mutation_started=True)) is False
    assert CLOSE_GUARD.close_run_proves_no_mutation([]) is False


def test_emergency_dispatch_authorization_requires_explicit_operator_allowlist() -> None:
    assert OPERATOR_AUTH.authorize_cleanup(
        event_name="schedule", actor="github-actions[bot]", trusted_operators=""
    ) is True
    assert OPERATOR_AUTH.authorize_cleanup(
        event_name="workflow_dispatch", actor="alice", trusted_operators="alice,bob"
    ) is True
    with pytest.raises(OPERATOR_AUTH.CleanupAuthorizationError, match="not in the trusted operator list"):
        OPERATOR_AUTH.authorize_cleanup(
            event_name="workflow_dispatch", actor="mallory", trusted_operators="alice,bob"
        )
    with pytest.raises(OPERATOR_AUTH.CleanupAuthorizationError, match="must be configured"):
        OPERATOR_AUTH.authorize_cleanup(
            event_name="workflow_dispatch", actor="alice", trusted_operators=""
        )
    with pytest.raises(OPERATOR_AUTH.CleanupAuthorizationError, match="invalid GitHub login"):
        OPERATOR_AUTH.authorize_cleanup(
            event_name="workflow_dispatch", actor="alice", trusted_operators="alice,invalid/name"
        )


def test_manual_cleanup_authorization_uses_the_rerunning_operator() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-hml-cleanup.yml").read_text(
        encoding="utf-8"
    )

    assert "REQUESTED_ACTOR: ${{ github.triggering_actor }}" in workflow
    assert OPERATOR_AUTH.authorize_cleanup(
        event_name="workflow_dispatch",
        actor="trusted-rerunner",
        trusted_operators="trusted-rerunner",
    ) is True
    with pytest.raises(OPERATOR_AUTH.CleanupAuthorizationError):
        OPERATOR_AUTH.authorize_cleanup(
            event_name="workflow_dispatch",
            actor="original-actor",
            trusted_operators="trusted-rerunner",
        )


def test_cleanup_workflow_documents_default_branch_promotion_and_operations_environment_refs() -> None:
    deployment = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")

    assert "HML_CLEANUP_TRUSTED_OPERATORS" in deployment
    assert "branch padrão" in deployment
    assert "`develop`" in deployment
    assert "operations" in deployment
