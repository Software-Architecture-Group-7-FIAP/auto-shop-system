from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LEDGER_SCRIPT = ROOT / ".github" / "scripts" / "lifecycle_session_ledger.py"
LEDGER_SPEC = importlib.util.spec_from_file_location("lifecycle_session_ledger", LEDGER_SCRIPT)
assert LEDGER_SPEC is not None and LEDGER_SPEC.loader is not None
LEDGER = importlib.util.module_from_spec(LEDGER_SPEC)
LEDGER_SPEC.loader.exec_module(LEDGER)
RESOLVER_SCRIPT = ROOT / ".github" / "scripts" / "resolve_lifecycle_session.py"
RESOLVER_SPEC = importlib.util.spec_from_file_location("resolve_lifecycle_session", RESOLVER_SCRIPT)
assert RESOLVER_SPEC is not None and RESOLVER_SPEC.loader is not None
RESOLVER = importlib.util.module_from_spec(RESOLVER_SPEC)
RESOLVER_SPEC.loader.exec_module(RESOLVER)


def test_authorization_records_the_configured_cross_repo_dispatch_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    state = {
        "status": "active",
        "stage": "hml",
        "session_mode": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "start_run_id": "123",
        "start_run_attempt": 1,
        "expires_at": now + 60,
        "ttl_epoch_seconds": now + 86400,
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(LEDGER, "_get_item", lambda _session_id, _record_key: state)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    for key, value in {
        "GITHUB_ACTOR": "trusted-operator",
        "LIFECYCLE_TRIGGERING_ACTOR": "trusted-operator",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW": "Coordinated environment start",
        "LIFECYCLE_TRUSTED_OPERATORS": "trusted-operator,dispatch-bot[bot]",
        "LIFECYCLE_CROSS_REPO_ACTOR": "dispatch-bot[bot]",
    }.items():
        monkeypatch.setenv(key, value)

    LEDGER.issue_dispatch_authorization(
        session_id="hml-2026-10-30",
        dispatch_id="a" * 32,
        action="open",
        repository="Software-Architecture-Group-7-FIAP/database-infra",
        workflow="Apply database staging",
        ref="main",
        inputs={
            "session_id": "hml-2026-10-30",
            "started_at": "2026-10-30T12:00:00Z",
            "session_mode": "hml",
            "lifecycle_dispatch_id": "a" * 32,
        },
    )

    assert writes[0]["Item"]["source_actor"] == {"S": "trusted-operator"}
    assert writes[0]["Item"]["dispatch_actor"] == {"S": "dispatch-bot[bot]"}


@pytest.mark.parametrize(
    ("requested_scope", "expected_scope"),
    [
        (None, "integrated"),
        ("integrated", "integrated"),
        ("infrastructure-only", "infrastructure-only"),
        ("release-validation", "release-validation"),
    ],
)
def test_open_persists_the_requested_hml_session_scope(
    monkeypatch: pytest.MonkeyPatch, requested_scope: str | None, expected_scope: str
) -> None:
    started_at = "2026-10-30T12:00:00Z"
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("123", 1))
    monkeypatch.setattr(
        LEDGER,
        "_session_values",
        lambda *_args: (
            datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 30, 14, 0, tzinfo=LEDGER.BRT),
            now + 60,
            now + 86400,
        ),
    )
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})

    options = {} if requested_scope is None else {"session_scope": requested_scope}
    LEDGER.authorize_open("hml-2026-10-30", "hml", started_at, "hml", **options)

    assert writes[0]["Item"]["session_scope"] == {"S": expected_scope}


def test_open_retry_aliases_reserved_operator_attribute_in_update_condition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_at = "2026-10-30T12:00:00Z"
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    stored = {
        "status": "active",
        "operator": "trusted-operator",
        "start_run_id": "123",
        "start_run_attempt": 1,
        "started_at": started_at,
        "stage": "hml",
        "session_scope": "infrastructure-only",
        "expires_at": now + 60,
    }
    updates: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("123", 2))
    monkeypatch.setattr(
        LEDGER,
        "_session_values",
        lambda *_args: (
            datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 30, 14, 0, tzinfo=LEDGER.BRT),
            now + 60,
            now + 86400,
        ),
    )
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)

    def capture_update(operation: str, request: dict[str, object]) -> dict[str, object]:
        if operation == "put-item":
            raise LEDGER.LedgerConflict("The state already exists.")
        updates.append(request)
        return {}

    monkeypatch.setattr(LEDGER, "_ddb", capture_update)
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args: stored)

    LEDGER.authorize_open(
        "hml-2026-10-30",
        "hml",
        started_at,
        "hml",
        session_scope="infrastructure-only",
    )

    assert len(updates) == 1
    assert updates[0]["ExpressionAttributeNames"] == {"#status": "status", "#operator": "operator"}
    assert "#operator = :actor" in str(updates[0]["ConditionExpression"])


@pytest.mark.parametrize("scope", ["infrastructure-only", "release-validation"])
def test_limited_session_scopes_are_rejected_for_prd(
    monkeypatch: pytest.MonkeyPatch, scope: str
) -> None:
    now = int(datetime(2026, 11, 1, 9, 30, tzinfo=timezone.utc).timestamp())
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("123", 1))
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})

    with pytest.raises(LEDGER.LedgerError, match="limited session scopes are HML-only"):
        LEDGER.authorize_open(
            "prd-2026-11-01",
            "prd",
            "2026-11-01T09:00:00Z",
            "prd-window",
            session_scope=scope,
        )

    assert writes == []


def test_open_replay_cannot_change_the_persisted_session_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    stored = {
        "status": "active",
        "operator": "trusted-operator",
        "start_run_id": "123",
        "start_run_attempt": 1,
        "started_at": "2026-10-30T12:00:00Z",
        "stage": "hml",
        "session_scope": "integrated",
        "expires_at": now + 60,
    }
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("123", 1))
    monkeypatch.setattr(
        LEDGER,
        "_session_values",
        lambda *_args: (
            datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 30, 14, 0, tzinfo=LEDGER.BRT),
            now + 60,
            now + 86400,
        ),
    )
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(LEDGER, "_ddb", lambda *_args: (_ for _ in ()).throw(LEDGER.LedgerConflict("exists")))
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args: stored)

    with pytest.raises(LEDGER.LedgerError, match="different or expired opening"):
        LEDGER.authorize_open(
            "hml-2026-10-30",
            "hml",
            "2026-10-30T12:00:00Z",
            "hml",
            session_scope="release-validation",
        )


@pytest.mark.parametrize(
    ("stored_scope", "expected_scope"),
    [("integrated", "integrated"), ("infrastructure-only", "infrastructure-only"), (None, "integrated")],
)
def test_session_scope_is_resolved_from_ledger_state(
    monkeypatch: pytest.MonkeyPatch, stored_scope: str | None, expected_scope: str
) -> None:
    state = {
        "status": "active",
        "stage": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
    }
    if stored_scope is not None:
        state["session_scope"] = stored_scope
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")

    assert LEDGER.resolve_session_scope(
        "hml-2026-10-30", "hml", "2026-10-30T12:00:00Z"
    ) == expected_scope


def test_session_scope_resolution_fails_closed_for_unknown_stored_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "status": "active",
        "stage": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "session_scope": "other",
    }
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")

    with pytest.raises(LEDGER.LedgerError, match="stored session scope is invalid"):
        LEDGER.resolve_session_scope("hml-2026-10-30", "hml", "2026-10-30T12:00:00Z")


def test_app_dispatch_cannot_claim_a_scope_different_from_the_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"stage": "hml", "session_scope": "release-validation"}
    authorization = {"action": "open"}
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(
        LEDGER,
        "_get_item",
        lambda _session_id, key, **_kwargs: authorization if key.startswith("AUTH#") else state,
    )
    for key, value in {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_WORKFLOW": "CD Staging",
        "GITHUB_REF": "refs/heads/develop",
    }.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(LEDGER.LedgerError, match="does not match the persisted lifecycle scope"):
        LEDGER.consume_dispatch_authorization(
            session_id="hml-2026-10-30",
            dispatch_id="a" * 32,
            repository="owner/repo",
            workflow="CD Staging",
            ref="refs/heads/develop",
            inputs={
                "session_id": "hml-2026-10-30",
                "lifecycle_dispatch_id": "a" * 32,
                "session_scope": "integrated",
            },
            expected_action="open",
        )


def test_app_dispatch_returns_the_persisted_scope_after_one_use_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    state = {
        "status": "active",
        "stage": "hml",
        "session_mode": "hml",
        "session_scope": "release-validation",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "start_run_id": "123",
        "start_run_attempt": 1,
        "expires_at": now + 60,
    }
    authorization = {
        "action": "open",
        "record_type": "authorization",
        "stage": "hml",
        "source_actor": "trusted-operator",
        "source_ref": "refs/heads/main",
        "source_workflow": "Coordinated environment start",
        "source_run_id": "123",
        "source_run_attempt": 1,
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(
        LEDGER,
        "_get_item",
        lambda _session_id, key: authorization if key.startswith("AUTH#") else state,
    )
    monkeypatch.setattr(LEDGER, "_validate_dispatch_actor", lambda *_args: "dispatch-bot[bot]")
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    for key, value in {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_WORKFLOW": "CD Staging",
        "GITHUB_REF": "refs/heads/develop",
    }.items():
        monkeypatch.setenv(key, value)

    scope = LEDGER.consume_dispatch_authorization(
        session_id="hml-2026-10-30",
        dispatch_id="a" * 32,
        repository="owner/repo",
        workflow="CD Staging",
        ref="refs/heads/develop",
        inputs={
            "session_id": "hml-2026-10-30",
            "started_at": "2026-10-30T12:00:00Z",
            "session_mode": "hml",
            "session_scope": "release-validation",
            "lifecycle_dispatch_id": "a" * 32,
        },
        expected_action="open",
    )

    assert scope == "release-validation"
    assert writes[0]["ExpressionAttributeValues"][":consumed"] == {"S": "consumed"}


def test_only_the_opening_or_closing_operator_can_resolve_scope_manually(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "status": "active",
        "stage": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "session_scope": "infrastructure-only",
    }
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "another-operator")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")

    with pytest.raises(LEDGER.LedgerError, match="only by its trusted lifecycle operator"):
        LEDGER.resolve_session_scope("hml-2026-10-30", "hml", "2026-10-30T12:00:00Z")


def test_dispatch_consumer_must_match_the_configured_actor_not_just_an_allowlisted_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in {
        "GITHUB_ACTOR": "another-trusted-operator",
        "LIFECYCLE_TRIGGERING_ACTOR": "another-trusted-operator",
        "LIFECYCLE_TRUSTED_OPERATORS": "another-trusted-operator,dispatch-bot[bot]",
    }.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(LEDGER.LedgerError, match="does not match the authorized cross-repository dispatch actor"):
        LEDGER._validate_dispatch_actor(
            {"dispatch_actor": "dispatch-bot[bot]", "source_actor": "trusted-operator"},
            {"operator": "trusted-operator"},
        )


def test_dispatch_consumer_rejects_a_different_current_triggering_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in {
        "GITHUB_ACTOR": "dispatch-bot[bot]",
        "LIFECYCLE_TRIGGERING_ACTOR": "trusted-operator",
        "LIFECYCLE_TRUSTED_OPERATORS": "trusted-operator,dispatch-bot[bot]",
    }.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(LEDGER.LedgerError, match="triggering actor does not match the original workflow actor"):
        LEDGER._validate_dispatch_actor(
            {"dispatch_actor": "dispatch-bot[bot]", "source_actor": "trusted-operator"},
            {"operator": "trusted-operator"},
        )


def test_operator_rejects_a_rerun_started_by_another_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {
        "GITHUB_ACTOR": "trusted-operator",
        "LIFECYCLE_TRIGGERING_ACTOR": "untrusted-rerunner",
        "LIFECYCLE_TRUSTED_OPERATORS": "trusted-operator",
    }.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(LEDGER.LedgerError, match="triggering actor does not match the original workflow actor"):
        LEDGER._operator()


def test_prd_session_expiry_is_five_hours_and_cleanup_reserves_teardown_and_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, local_end, expires_at, _ = LEDGER._session_values(
        "prd-2026-11-01", "prd", "2026-11-01T09:00:00Z"
    )

    assert local_end.hour == 11
    assert expires_at == int(datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc).timestamp())

    cleanup_workflow = (ROOT / ".github" / "workflows" / "lifecycle-cleanup.yml").read_text(encoding="utf-8")
    assert 'cron: "0 0-1,14-23 * * *"' in cleanup_workflow

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            current = datetime(2026, 11, 1, 9, 30, tzinfo=timezone.utc)
            return current.astimezone(tz) if tz is not None else current.replace(tzinfo=None)

    output_path = tmp_path / "resolver-output"
    monkeypatch.setattr(RESOLVER, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "resolve_lifecycle_session.py",
            "--action",
            "start",
            "--stage",
            "prd",
            "--github-output",
            str(output_path),
        ],
    )

    assert RESOLVER.main() == 0
    output = dict(line.split("=", maxsplit=1) for line in output_path.read_text(encoding="utf-8").splitlines())
    assert output["session_end_utc"] == "2026-11-01T14:00:00Z"
    assert output["teardown_deadline_utc"] == "2026-11-02T01:40:00Z"
    assert output["audit_start_utc"] == "2026-11-02T01:45:00Z"
    assert output["cleanup_end_utc"] == "2026-11-02T02:00:00Z"
