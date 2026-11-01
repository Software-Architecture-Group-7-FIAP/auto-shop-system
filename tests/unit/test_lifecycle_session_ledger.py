from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.parametrize("prefix", ["", "aws: [ERROR]: "])
def test_ddb_error_reports_only_sanitized_aws_error_code(
    monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    monkeypatch.setenv("LIFECYCLE_TABLE_NAME", "lifecycle-ledger")
    monkeypatch.setattr(
        LEDGER.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=254,
            stderr=(
                f"{prefix}An error occurred (ValidationException) when calling the UpdateItem operation: "
                "sensitive request detail"
            ),
            stdout="",
        ),
    )

    with pytest.raises(LEDGER.LedgerError) as error:
        LEDGER._ddb("update-item", {"Key": {}})

    assert "ValidationException" in str(error.value)
    assert "sensitive request detail" not in str(error.value)


def test_ddb_error_does_not_report_unrecognized_stderr_as_error_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIFECYCLE_TABLE_NAME", "lifecycle-ledger")
    monkeypatch.setattr(
        LEDGER.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=2,
            stderr="diagnostic includes account 123456789012 and other private data",
            stdout="",
        ),
    )

    with pytest.raises(LEDGER.LedgerError) as error:
        LEDGER._ddb("update-item", {"Key": {}})

    assert "123456789012" not in str(error.value)
    assert "private data" not in str(error.value)


def test_ddb_conditional_failure_remains_a_ledger_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFECYCLE_TABLE_NAME", "lifecycle-ledger")
    monkeypatch.setattr(
        LEDGER.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=254,
            stderr=(
                "An error occurred (ConditionalCheckFailedException) when calling the UpdateItem operation: "
                "private condition details"
            ),
            stdout="",
        ),
    )

    with pytest.raises(LEDGER.LedgerConflict) as error:
        LEDGER._ddb("update-item", {"Key": {}})

    assert "private condition details" not in str(error.value)


@pytest.mark.parametrize("ref", ["main", "refs/heads/main"])
def test_authorization_records_the_configured_cross_repo_dispatch_actor(
    monkeypatch: pytest.MonkeyPatch, ref: str
) -> None:
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
        ref=ref,
        inputs={
            "session_id": "hml-2026-10-30",
            "started_at": "2026-10-30T12:00:00Z",
            "session_mode": "hml",
            "lifecycle_dispatch_id": "a" * 32,
        },
    )

    assert writes[0]["Item"]["source_actor"] == {"S": "trusted-operator"}
    assert writes[0]["Item"]["dispatch_actor"] == {"S": "dispatch-bot[bot]"}
    assert writes[0]["Item"]["target_ref"] == {"S": "refs/heads/main"}
    assert writes[0]["Item"]["emergency_capability_verified"] == {"S": "false"}


def test_emergency_develop_close_authorization_records_the_verified_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    state = {
        "status": "closing",
        "stage": "hml",
        "session_mode": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "close_actor": "trusted-operator",
        "close_run_id": "123",
        "close_run_attempt": 1,
        "ttl_epoch_seconds": now + 86400,
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(LEDGER, "_get_item", lambda _session_id, _record_key: state)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    for key, value in {
        "GITHUB_ACTOR": "trusted-operator",
        "LIFECYCLE_TRIGGERING_ACTOR": "trusted-operator",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/develop",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW": LEDGER.STOP_WORKFLOW_NAME,
        "LIFECYCLE_EMERGENCY_CAPABILITY_VERIFIED": "true",
        "CLOSE_REQUEST_ID": "emergency-42",
        "LIFECYCLE_TRUSTED_OPERATORS": "trusted-operator,dispatch-bot[bot]",
        "LIFECYCLE_CROSS_REPO_ACTOR": "dispatch-bot[bot]",
    }.items():
        monkeypatch.setenv(key, value)

    LEDGER.issue_dispatch_authorization(
        session_id="hml-2026-10-30",
        dispatch_id="b" * 32,
        action="close",
        repository="owner/infra",
        workflow="apply.yml",
        ref="main",
        inputs={
            "session_id": "hml-2026-10-30",
            "started_at": "2026-10-30T12:00:00Z",
            "session_mode": "hml",
            "lifecycle_dispatch_id": "b" * 32,
        },
    )

    assert writes[0]["Item"]["source_ref"] == {"S": "refs/heads/develop"}
    assert writes[0]["Item"]["source_workflow"] == {"S": LEDGER.STOP_WORKFLOW_NAME}
    assert writes[0]["Item"]["emergency_capability_verified"] == {"S": "true"}


def test_emergency_develop_audit_authorization_records_the_verified_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    state = {
        "status": "closing",
        "stage": "hml",
        "session_mode": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "close_actor": "trusted-operator",
        "close_run_id": "123",
        "close_run_attempt": 1,
        "ttl_epoch_seconds": now + 86400,
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(LEDGER, "_get_item", lambda _session_id, _record_key: state)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    for key, value in {
        "GITHUB_ACTOR": "trusted-operator",
        "LIFECYCLE_TRIGGERING_ACTOR": "trusted-operator",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/develop",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW": LEDGER.STOP_WORKFLOW_NAME,
        "LIFECYCLE_EMERGENCY_CAPABILITY_VERIFIED": "true",
        "CLOSE_REQUEST_ID": "emergency-42",
        "LIFECYCLE_TRUSTED_OPERATORS": "trusted-operator,dispatch-bot[bot]",
        "LIFECYCLE_CROSS_REPO_ACTOR": "dispatch-bot[bot]",
    }.items():
        monkeypatch.setenv(key, value)

    LEDGER.issue_dispatch_authorization(
        session_id="hml-2026-10-30",
        dispatch_id="7" * 32,
        action="audit",
        repository="owner/infra",
        workflow="audit.yml",
        ref="main",
        inputs={
            "session_id": "hml-2026-10-30",
            "started_at": "2026-10-30T12:00:00Z",
            "session_mode": "hml",
            "lifecycle_dispatch_id": "7" * 32,
        },
    )

    assert writes[0]["Item"]["action"] == {"S": "audit"}
    assert writes[0]["Item"]["emergency_capability_verified"] == {"S": "true"}


def test_normal_develop_close_authorization_records_its_consumed_source_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    session_id = "hml-2026-10-30"
    incoming_dispatch_id = "8" * 32
    state = {
        "status": "closing",
        "stage": "hml",
        "session_mode": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "close_actor": "trusted-operator",
        "close_run_id": "456",
        "close_run_attempt": 1,
        "ttl_epoch_seconds": now + 86400,
    }
    source_authorization = {
        "action": "close",
        "status": "consumed",
        "source_actor": "trusted-operator",
        "source_workflow": "Coordinated environment start",
        "source_ref": "refs/heads/main",
        "dispatch_actor": "dispatch-bot[bot]",
        "consumer_actor": "dispatch-bot[bot]",
        "consumer_run_id": "456",
        "consumer_run_attempt": 1,
        "target_repository": "owner/auto-shop-system",
        "target_workflow": LEDGER.STOP_WORKFLOW_NAME,
        "target_ref": "refs/heads/develop",
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(LEDGER, "_inputs_from_event", lambda: {
        "session_id": session_id,
        "started_at": state["started_at"],
        "session_mode": "hml",
        "lifecycle_dispatch_id": incoming_dispatch_id,
    })
    monkeypatch.setattr(
        LEDGER,
        "_get_item",
        lambda _session_id, key, **_kwargs: state if key == "STATE" else source_authorization,
    )
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    for key, value in {
        "GITHUB_ACTOR": "dispatch-bot[bot]",
        "LIFECYCLE_TRIGGERING_ACTOR": "dispatch-bot[bot]",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "owner/auto-shop-system",
        "GITHUB_REF": "refs/heads/develop",
        "GITHUB_RUN_ID": "456",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW": LEDGER.STOP_WORKFLOW_NAME,
        "LIFECYCLE_TRUSTED_OPERATORS": "trusted-operator,dispatch-bot[bot]",
        "LIFECYCLE_CROSS_REPO_ACTOR": "dispatch-bot[bot]",
    }.items():
        monkeypatch.setenv(key, value)

    LEDGER.issue_dispatch_authorization(
        session_id=session_id,
        dispatch_id="9" * 32,
        action="close",
        repository="owner/infra",
        workflow="apply.yml",
        ref="main",
        inputs={
            "session_id": session_id,
            "started_at": state["started_at"],
            "session_mode": "hml",
            "lifecycle_dispatch_id": "9" * 32,
        },
    )

    assert writes[0]["Item"]["emergency_capability_verified"] == {"S": "false"}
    assert writes[0]["Item"]["source_close_dispatch_id"] == {"S": incoming_dispatch_id}
    assert writes[0]["Item"]["source_close_authorization_verified"] == {"S": "true"}
    assert writes[0]["Item"]["source_repository"] == {"S": "owner/auto-shop-system"}


@pytest.mark.parametrize(
    ("action", "verified", "error"),
    [
        ("open", "true", "allowed only from main or a verified emergency close/audit"),
        ("close", "false", "consumed normal close or verified emergency capability"),
        ("audit", "false", "consumed normal close or verified emergency capability"),
    ],
)
def test_develop_source_rejects_non_emergency_or_non_close_authorization(
    monkeypatch: pytest.MonkeyPatch, action: str, verified: str, error: str
) -> None:
    for key, value in {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/develop",
        "GITHUB_WORKFLOW": LEDGER.STOP_WORKFLOW_NAME,
        "LIFECYCLE_EMERGENCY_CAPABILITY_VERIFIED": verified,
        "CLOSE_REQUEST_ID": "emergency-42",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(LEDGER, "_inputs_from_event", lambda: {})

    with pytest.raises(LEDGER.LedgerError, match=error):
        LEDGER.issue_dispatch_authorization(
            session_id="hml-2026-10-30",
            dispatch_id="c" * 32,
            action=action,
            repository="owner/infra",
            workflow="apply.yml",
            ref="main",
            inputs={},
        )


def test_issue_dispatch_cli_parses_and_forwards_exact_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issued: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "issue_dispatch_authorization", lambda **kwargs: issued.append(kwargs))
    monkeypatch.setattr(
        LEDGER.sys,
        "argv",
        [
            "lifecycle_session_ledger.py",
            "issue-dispatch",
            "--session-id",
            "hml-2026-10-30",
            "--dispatch-id",
            "d" * 32,
            "--action",
            "close",
            "--repository",
            "owner/infra",
            "--workflow",
            "apply.yml",
            "--ref",
            "main",
            "--inputs",
            '{"session_id":"hml-2026-10-30","started_at":"2026-10-30T12:00:00Z","session_mode":"hml","lifecycle_dispatch_id":"'
            + "d" * 32
            + '"}',
        ],
    )

    assert LEDGER.main() == 0
    assert issued == [
        {
            "session_id": "hml-2026-10-30",
            "dispatch_id": "d" * 32,
            "action": "close",
            "repository": "owner/infra",
            "workflow": "apply.yml",
            "ref": "main",
            "inputs": {
                "session_id": "hml-2026-10-30",
                "started_at": "2026-10-30T12:00:00Z",
                "session_mode": "hml",
                "lifecycle_dispatch_id": "d" * 32,
            },
        }
    ]


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


def test_safe_retry_handoff_transfers_only_the_matching_active_hml_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_at = "2026-10-30T12:00:00Z"
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    stored = {
        "status": "active",
        "operator": "trusted-operator",
        "start_run_id": "123",
        "start_run_attempt": 2,
        "started_at": started_at,
        "stage": "hml",
        "session_mode": "hml",
        "session_scope": "infrastructure-only",
        "expires_at": now + 60,
    }
    updates: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
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
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: stored)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: updates.append(request) or {})
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Coordinated environment start")

    LEDGER.authorize_open(
        "hml-2026-10-30",
        "hml",
        started_at,
        "hml",
        session_scope="infrastructure-only",
        safe_retry_source_run_id="123",
    )

    assert len(updates) == 1
    assert updates[0]["ExpressionAttributeNames"]["#operator"] == "operator"
    assert "#start_run_id = :source_run" in str(updates[0]["ConditionExpression"])
    assert "#start_run_attempt = :source_attempt" in str(updates[0]["ConditionExpression"])
    assert "#expires_at = :expires AND #expires_at > :now" in str(updates[0]["ConditionExpression"])
    assert "#start_run_id = :new_run" in str(updates[0]["UpdateExpression"])
    assert updates[0]["ExpressionAttributeValues"][":new_run"] == {"S": "456"}
    assert updates[0]["ExpressionAttributeValues"][":source_run"] == {"S": "123"}
    assert updates[0]["ExpressionAttributeValues"][":source_attempt"] == {"N": "2"}


def test_safe_retry_handoff_reopens_only_a_matching_unclaimed_closed_hml_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_at = "2026-10-30T12:00:00Z"
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    stored = {
        "status": "closed",
        "closed_at": now - 30,
        "operator": "trusted-operator",
        "start_run_id": "123",
        "start_run_attempt": 2,
        "started_at": started_at,
        "stage": "hml",
        "session_mode": "hml",
        "session_scope": "infrastructure-only",
        "expires_at": now + 60,
    }
    updates: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
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
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: stored)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: updates.append(request) or {})
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Coordinated environment start")

    LEDGER.authorize_open(
        "hml-2026-10-30",
        "hml",
        started_at,
        "hml",
        session_scope="infrastructure-only",
        safe_retry_source_run_id="123",
    )

    assert len(updates) == 1
    assert "REMOVE #closed_at" in str(updates[0]["UpdateExpression"])
    assert "#status = :closed" in str(updates[0]["ConditionExpression"])
    assert "#closed_at = :closed_at" in str(updates[0]["ConditionExpression"])
    assert "attribute_not_exists(#close_run_id)" in str(updates[0]["ConditionExpression"])
    assert "attribute_not_exists(close_run_id)" not in str(updates[0]["ConditionExpression"])
    assert updates[0]["ExpressionAttributeNames"]["#closed_at"] == "closed_at"
    assert updates[0]["ExpressionAttributeNames"]["#close_run_id"] == "close_run_id"
    assert updates[0]["ExpressionAttributeValues"][":closed_at"] == {"N": str(now - 30)}


def test_safe_retry_handoff_does_not_reopen_a_coordinator_closed_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    stored = {
        "status": "closed",
        "closed_at": now - 30,
        "close_run_id": "stop-run",
        "close_actor": "trusted-operator",
        "close_run_attempt": 1,
        "operator": "trusted-operator",
        "start_run_id": "123",
        "start_run_attempt": 2,
        "started_at": "2026-10-30T12:00:00Z",
        "stage": "hml",
        "session_mode": "hml",
        "session_scope": "infrastructure-only",
        "expires_at": now + 60,
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
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
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: stored)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Coordinated environment start")

    with pytest.raises(LEDGER.LedgerError, match="does not match the verified failed opening run"):
        LEDGER.authorize_open(
            "hml-2026-10-30",
            "hml",
            "2026-10-30T12:00:00Z",
            "hml",
            session_scope="infrastructure-only",
            safe_retry_source_run_id="123",
        )

    assert writes == []


def test_safe_retry_handoff_is_restricted_to_the_exact_start_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
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
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Other lifecycle start")

    with pytest.raises(LEDGER.LedgerError, match="limited to the guarded HML infrastructure-only start"):
        LEDGER.authorize_open(
            "hml-2026-10-30",
            "hml",
            "2026-10-30T12:00:00Z",
            "hml",
            session_scope="infrastructure-only",
            safe_retry_source_run_id="123",
        )


def test_safe_retry_handoff_rejects_a_ledger_owned_by_a_different_failed_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    stored = {
        "status": "active",
        "operator": "trusted-operator",
        "start_run_id": "999",
        "start_run_attempt": 1,
        "started_at": "2026-10-30T12:00:00Z",
        "stage": "hml",
        "session_mode": "hml",
        "session_scope": "infrastructure-only",
        "expires_at": now + 60,
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
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
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: stored)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Coordinated environment start")

    with pytest.raises(LEDGER.LedgerError, match="does not match the verified failed opening run"):
        LEDGER.authorize_open(
            "hml-2026-10-30",
            "hml",
            "2026-10-30T12:00:00Z",
            "hml",
            session_scope="infrastructure-only",
            safe_retry_source_run_id="123",
        )

    assert writes == []


def test_safe_retry_rerun_keeps_the_current_run_as_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_at = "2026-10-30T12:00:00Z"
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    stored = {
        "status": "active",
        "operator": "trusted-operator",
        "start_run_id": "456",
        "start_run_attempt": 1,
        "started_at": started_at,
        "stage": "hml",
        "session_mode": "hml",
        "session_scope": "infrastructure-only",
        "expires_at": now + 60,
    }
    updates: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_require_main_branch", lambda: None)
    monkeypatch.setattr(LEDGER, "_operator", lambda **_kwargs: "trusted-operator")
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 2))
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
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: stored)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Coordinated environment start")

    LEDGER.authorize_open(
        "hml-2026-10-30",
        "hml",
        started_at,
        "hml",
        session_scope="infrastructure-only",
        safe_retry_source_run_id="123",
    )

    assert len(updates) == 1
    assert updates[0]["UpdateExpression"] == "SET start_run_attempt = :attempt"
    assert updates[0]["ExpressionAttributeValues"][":attempt"] == {"N": "2"}


def test_old_child_authorization_cannot_be_used_after_safe_retry_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    state = {
        "status": "active",
        "stage": "hml",
        "session_mode": "hml",
        "session_scope": "infrastructure-only",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "start_run_id": "456",
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
        "source_run_attempt": 2,
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("789", 1))
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(
        LEDGER,
        "_get_item",
        lambda _session_id, key, **_kwargs: authorization if key.startswith("AUTH#") else state,
    )
    monkeypatch.setattr(LEDGER, "_validate_dispatch_actor", lambda *_args: "dispatch-bot[bot]")
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    for key, value in {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "owner/k8s-infra",
        "GITHUB_WORKFLOW": "CI",
        "GITHUB_REF": "refs/heads/main",
    }.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(LEDGER.LedgerError, match="not issued by the active session-opening run"):
        LEDGER.consume_dispatch_authorization(
            session_id="hml-2026-10-30",
            dispatch_id="a" * 32,
            repository="owner/k8s-infra",
            workflow="CI",
            ref="refs/heads/main",
            inputs={
                "session_id": "hml-2026-10-30",
                "started_at": "2026-10-30T12:00:00Z",
                "session_mode": "hml",
                "lifecycle_dispatch_id": "a" * 32,
            },
            expected_action="open",
        )

    assert writes == []


@pytest.mark.parametrize(("action", "expected_action"), [("close", "stop"), ("audit", "audit")])
def test_consumer_accepts_verified_develop_close_proof_for_close_or_audit(
    monkeypatch: pytest.MonkeyPatch, action: str, expected_action: str
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    source_close_dispatch_id = "8" * 32
    state = {
        "status": "closing",
        "stage": "hml",
        "session_mode": "hml",
        "session_scope": "infrastructure-only",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
        "close_actor": "trusted-operator",
        "close_run_id": "123",
        "close_run_attempt": 1,
    }
    authorization = {
        "action": action,
        "record_type": "authorization",
        "stage": "hml",
        "source_actor": "trusted-operator",
        "dispatch_actor": "dispatch-bot[bot]",
        "source_ref": "refs/heads/develop",
        "source_workflow": LEDGER.STOP_WORKFLOW_NAME,
        "source_run_id": "123",
        "source_run_attempt": 1,
        "source_repository": "owner/auto-shop-system",
        "emergency_capability_verified": "false",
        "source_close_dispatch_id": source_close_dispatch_id,
        "source_close_authorization_verified": "true",
    }
    source_close_authorization = {
        "action": "close",
        "status": "consumed",
        "source_actor": "trusted-operator",
        "source_workflow": "Coordinated environment start",
        "source_ref": "refs/heads/main",
        "dispatch_actor": "dispatch-bot[bot]",
        "consumer_actor": "dispatch-bot[bot]",
        "consumer_run_id": "123",
        "consumer_run_attempt": 1,
        "target_repository": "owner/auto-shop-system",
        "target_workflow": LEDGER.STOP_WORKFLOW_NAME,
        "target_ref": "refs/heads/develop",
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(
        LEDGER,
        "_get_item",
        lambda _session_id, key, **_kwargs: (
            source_close_authorization
            if key == f"AUTH#DISPATCH#{source_close_dispatch_id}"
            else authorization
            if key.startswith("AUTH#")
            else state
        ),
    )
    monkeypatch.setattr(LEDGER, "_validate_dispatch_actor", lambda *_args: "dispatch-bot[bot]")
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    for key, value in {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "owner/infra",
        "GITHUB_WORKFLOW": "CI",
        "GITHUB_REF": "refs/heads/main",
    }.items():
        monkeypatch.setenv(key, value)

    session_scope = LEDGER.consume_dispatch_authorization(
        session_id="hml-2026-10-30",
        dispatch_id="e" * 32,
        repository="owner/infra",
        workflow="CI",
        ref="refs/heads/main",
        inputs={
            "session_id": "hml-2026-10-30",
            "started_at": "2026-10-30T12:00:00Z",
            "session_mode": "hml",
            "lifecycle_dispatch_id": "e" * 32,
        },
        expected_action=expected_action,
    )

    assert session_scope == "infrastructure-only"
    assert writes[0]["ExpressionAttributeValues"][":consumed"] == {"S": "consumed"}


def test_consumer_rejects_develop_emergency_proof_for_non_close_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    state = {
        "status": "active",
        "stage": "hml",
        "session_mode": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "trusted-operator",
    }
    authorization = {
        "action": "open",
        "record_type": "authorization",
        "stage": "hml",
        "source_actor": "trusted-operator",
        "source_ref": "refs/heads/develop",
        "source_workflow": LEDGER.STOP_WORKFLOW_NAME,
        "source_run_id": "123",
        "source_run_attempt": 1,
        "emergency_capability_verified": "true",
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(
        LEDGER,
        "_get_item",
        lambda _session_id, key, **_kwargs: authorization if key.startswith("AUTH#") else state,
    )
    monkeypatch.setattr(LEDGER, "_validate_dispatch_actor", lambda *_args: "dispatch-bot[bot]")
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    for key, value in {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "owner/infra",
        "GITHUB_WORKFLOW": "CI",
        "GITHUB_REF": "refs/heads/main",
    }.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(
        LEDGER.LedgerError,
        match="valid only for a develop-branch close or audit authorization",
    ):
        LEDGER.consume_dispatch_authorization(
            session_id="hml-2026-10-30",
            dispatch_id="f" * 32,
            repository="owner/infra",
            workflow="CI",
            ref="refs/heads/main",
            inputs={
                "session_id": "hml-2026-10-30",
                "started_at": "2026-10-30T12:00:00Z",
                "session_mode": "hml",
                "lifecycle_dispatch_id": "f" * 32,
            },
            expected_action="open",
        )

    assert writes == []


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
    monkeypatch.setattr(LEDGER, "_require_stop_coordinator_branch", lambda **_kwargs: None)
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
    monkeypatch.setattr(LEDGER, "_require_stop_coordinator_branch", lambda **_kwargs: None)
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
    monkeypatch.setattr(LEDGER, "_require_stop_coordinator_branch", lambda **_kwargs: None)
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


def _set_verified_emergency_stop_context(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {
        "GITHUB_ACTOR": "emergency-operator",
        "LIFECYCLE_TRIGGERING_ACTOR": "emergency-operator",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_WORKFLOW": LEDGER.STOP_WORKFLOW_NAME,
        "GITHUB_REF": "refs/heads/develop",
        "GITHUB_RUN_ID": "456",
        "GITHUB_RUN_ATTEMPT": "1",
        "LIFECYCLE_EMERGENCY_CAPABILITY_VERIFIED": "true",
        "CLOSE_REQUEST_ID": "emergency-42",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LIFECYCLE_TRUSTED_OPERATORS", raising=False)


def test_emergency_capability_allows_scope_resolution_without_operator_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "status": "active",
        "stage": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "opening-operator",
        "close_actor": "opening-operator",
        "session_scope": "infrastructure-only",
    }
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(
        LEDGER,
        "_session_values",
        lambda *_args: (
            datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 30, 14, 0, tzinfo=timezone.utc),
            0,
            0,
        ),
    )
    _set_verified_emergency_stop_context(monkeypatch)

    assert LEDGER.resolve_session_scope(
        "hml-2026-10-30", "hml", "2026-10-30T12:00:00Z"
    ) == "infrastructure-only"


def test_emergency_capability_allows_begin_close_without_operator_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = int(datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc).timestamp())
    state = {
        "status": "active",
        "stage": "hml",
        "started_at": "2026-10-30T12:00:00Z",
        "operator": "opening-operator",
        "close_actor": "opening-operator",
        "session_scope": "infrastructure-only",
        "cleanup_deadline_at": now - 1,
    }
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(
        LEDGER,
        "_session_values",
        lambda *_args: (
            datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 30, 14, 0, tzinfo=timezone.utc),
            now + 60,
            now + 86400,
        ),
    )
    monkeypatch.setattr(LEDGER.time, "time", lambda: now)
    monkeypatch.setattr(LEDGER, "_get_item", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    _set_verified_emergency_stop_context(monkeypatch)

    LEDGER.begin_close(
        "hml-2026-10-30", "hml", "2026-10-30T12:00:00Z", dispatch_id=""
    )

    assert writes[0]["ExpressionAttributeValues"][":actor"] == {"S": "opening-operator"}
    assert writes[0]["ExpressionAttributeValues"][":lease"]["N"] == str(now + LEDGER.CLOSE_LEASE_SECONDS)


def test_emergency_capability_allows_close_bookkeeping_without_operator_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(LEDGER, "_run_identity", lambda: ("456", 1))
    monkeypatch.setattr(LEDGER.time, "time", lambda: 1_798_000_000)
    monkeypatch.setattr(LEDGER, "_ddb", lambda _operation, request: writes.append(request) or {})
    _set_verified_emergency_stop_context(monkeypatch)

    LEDGER.finalize_close("hml-2026-10-30")
    LEDGER.record_close_step("hml-2026-10-30", "database", "success", "destroyed")

    assert len(writes) == 2


def test_emergency_operator_bypass_requires_the_exact_verified_stop_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_verified_emergency_stop_context(monkeypatch)
    monkeypatch.setenv("GITHUB_WORKFLOW", "Unrelated workflow")

    with pytest.raises(LEDGER.LedgerError, match="LIFECYCLE_TRUSTED_OPERATORS is required"):
        LEDGER._operator(allow_emergency_stop=True)



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
