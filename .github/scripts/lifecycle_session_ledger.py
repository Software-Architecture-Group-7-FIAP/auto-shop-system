#!/usr/bin/env python3
"""Manage short-lived lifecycle authorizations in the DynamoDB session ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BRT = ZoneInfo("America/Sao_Paulo")
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SESSION_PATTERN = re.compile(r"^(hml|prd)-(\d{4}-\d{2}-\d{2})$")
DISPATCH_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
RUN_ID_PATTERN = re.compile(r"^[1-9][0-9]{0,19}$")
ACTOR_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,39}(?:\[bot\])?$")
MAX_SESSION = timedelta(hours=5)
AUTH_TTL_SECONDS = 15 * 60
AUDIT_RETENTION_SECONDS = 30 * 24 * 60 * 60
CLOSE_LEASE_SECONDS = 6 * 60 * 60
GSI_NAME = "status-expiry-index"
SESSION_SCOPES = {"integrated", "infrastructure-only", "release-validation"}


class LedgerError(ValueError):
    """Raised when lifecycle ledger authorization cannot be proven."""


class LedgerConflict(LedgerError):
    """Raised when a conditional DynamoDB write loses its compare-and-swap."""


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise LedgerError(f"{name} is required; lifecycle authorization fails closed.")
    return value


def _require_original_actor() -> str:
    actor = _required_environment("GITHUB_ACTOR")
    triggering_actor = _required_environment("LIFECYCLE_TRIGGERING_ACTOR")
    if triggering_actor != actor:
        raise LedgerError("The triggering actor does not match the original workflow actor.")
    if not ACTOR_PATTERN.fullmatch(actor):
        raise LedgerError("The GitHub actor is malformed.")
    return actor


def _ddb(operation: str, request: dict[str, Any], *, paginate: bool = True) -> dict[str, Any]:
    table_name = _required_environment("LIFECYCLE_TABLE_NAME")
    request = {"TableName": table_name, **request}
    with tempfile.TemporaryDirectory(prefix="lifecycle-ledger-") as temporary_directory:
        request_path = Path(temporary_directory) / "request.json"
        request_path.write_text(json.dumps(request, separators=(",", ":")), encoding="utf-8")
        try:
            command = [
                    "aws",
                    "dynamodb",
                    operation,
                    "--cli-input-json",
                    f"file://{request_path}",
                    "--output",
                    "json",
                ]
            if not paginate:
                command.append("--no-paginate")
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=45,
                env={**os.environ, "AWS_PAGER": ""},
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LedgerError(f"DynamoDB {operation} did not complete; lifecycle authorization fails closed.") from error
    if result.returncode != 0:
        if "ConditionalCheckFailedException" in result.stderr:
            raise LedgerConflict(f"DynamoDB {operation} condition did not match.")
        raise LedgerError(f"DynamoDB {operation} was denied or failed; lifecycle authorization fails closed.")
    try:
        decoded = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise LedgerError("DynamoDB returned an invalid response; lifecycle authorization fails closed.") from error
    if not isinstance(decoded, dict):
        raise LedgerError("DynamoDB returned an invalid response; lifecycle authorization fails closed.")
    return decoded


def _s(value: str) -> dict[str, str]:
    return {"S": value}


def _n(value: int) -> dict[str, str]:
    return {"N": str(value)}


def _key(session_id: str, record_key: str) -> dict[str, dict[str, str]]:
    return {"session_id": _s(session_id), "record_key": _s(record_key)}


def _decode_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise LedgerError("The lifecycle ledger item is missing; authorization fails closed.")
    result: dict[str, Any] = {}
    for name, value in item.items():
        if not isinstance(value, dict):
            continue
        if "S" in value:
            result[name] = str(value["S"])
        elif "N" in value:
            result[name] = int(value["N"])
        elif "BOOL" in value:
            result[name] = bool(value["BOOL"])
    return result


def _get_item(session_id: str, record_key: str, *, consistent: bool = True) -> dict[str, Any]:
    response = _ddb(
        "get-item",
        {
            "Key": _key(session_id, record_key),
            "ConsistentRead": consistent,
        },
    )
    return _decode_item(response.get("Item"))


def _canonical_input_hash(inputs: dict[str, str]) -> str:
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_github_ref(ref: str) -> str:
    """Store workflow_dispatch refs in the same form exposed as GITHUB_REF."""
    if ref.startswith("refs/"):
        return ref
    return f"refs/heads/{ref}"


def _session_scope(state: dict[str, Any]) -> str:
    scope = state.get("session_scope", "integrated")
    if scope not in SESSION_SCOPES or (state.get("stage") != "hml" and scope != "integrated"):
        raise LedgerError("The stored session scope is invalid; lifecycle authorization fails closed.")
    return str(scope)


def _validate_dispatch_scope(
    state: dict[str, Any],
    inputs: dict[str, str],
    *,
    required: bool = False,
) -> str:
    stored_scope = _session_scope(state)
    requested_scope = inputs.get("session_scope")
    if required and requested_scope is None:
        raise LedgerError("The app deployment dispatch must include its persisted session scope.")
    if requested_scope is not None and requested_scope != stored_scope:
        raise LedgerError("The dispatch session scope does not match the persisted lifecycle scope.")
    return stored_scope


def _session_values(session_id: str, stage: str, started_at: str) -> tuple[datetime, datetime, int, int]:
    match = SESSION_PATTERN.fullmatch(session_id)
    if match is None or match.group(1) != stage:
        raise LedgerError("The lifecycle session ID and stage do not match.")
    try:
        local_day = datetime.strptime(match.group(2), "%Y-%m-%d").date()
        parsed_start = datetime.strptime(started_at, UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise LedgerError("The lifecycle session date or UTC start is malformed.") from error
    if parsed_start.strftime(UTC_FORMAT) != started_at or parsed_start.astimezone(BRT).date() != local_day:
        raise LedgerError("The lifecycle session start does not match its BRT session date.")
    local_start = parsed_start.astimezone(BRT)
    if stage == "prd" and local_start.time().replace(tzinfo=None).isoformat() != "06:00:00":
        raise LedgerError("PRD lifecycle sessions must start at 06:00 BRT.")
    if stage == "hml" and not (7 <= local_start.hour <= 17):
        raise LedgerError("HML lifecycle sessions must start between 07:00 and 17:00 BRT.")
    local_end = min(
        local_start + MAX_SESSION,
        datetime.combine(local_day, datetime.strptime("22:00", "%H:%M").time(), tzinfo=BRT),
    )
    cleanup_end = datetime.combine(local_day, datetime.strptime("23:00", "%H:%M").time(), tzinfo=BRT)
    if local_end <= local_start:
        raise LedgerError("The lifecycle session has no positive operating window.")
    expires_at = int(local_end.astimezone(timezone.utc).timestamp())
    cleanup_deadline = int(cleanup_end.astimezone(timezone.utc).timestamp())
    ttl = cleanup_deadline + AUDIT_RETENTION_SECONDS
    return parsed_start, local_end, expires_at, ttl


def _operator(*, allow_scheduled_stop: bool = False) -> str:
    actor = _require_original_actor()
    if (
        allow_scheduled_stop
        and os.environ.get("GITHUB_EVENT_NAME") == "schedule"
        and os.environ.get("GITHUB_WORKFLOW") == "Coordinated environment stop"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
    ):
        return actor
    raw_allowlist = _required_environment("LIFECYCLE_TRUSTED_OPERATORS")
    allowlist = {entry.strip() for entry in raw_allowlist.split(",") if entry.strip()}
    if not allowlist or actor not in allowlist:
        raise LedgerError("The GitHub actor is not in LIFECYCLE_TRUSTED_OPERATORS.")
    return actor


def _configured_dispatch_actor() -> str:
    _require_original_actor()
    actor = _required_environment("LIFECYCLE_CROSS_REPO_ACTOR")
    if not ACTOR_PATTERN.fullmatch(actor):
        raise LedgerError("LIFECYCLE_CROSS_REPO_ACTOR is malformed.")
    raw_allowlist = _required_environment("LIFECYCLE_TRUSTED_OPERATORS")
    allowlist = {entry.strip() for entry in raw_allowlist.split(",") if entry.strip()}
    if actor not in allowlist:
        raise LedgerError("LIFECYCLE_CROSS_REPO_ACTOR must be present in LIFECYCLE_TRUSTED_OPERATORS.")
    return actor


def _validate_dispatch_actor(authorization: dict[str, Any], state: dict[str, Any]) -> str:
    actor = _require_original_actor()
    expected_actor = authorization.get("dispatch_actor")
    source_actor = authorization.get("source_actor")
    if not isinstance(expected_actor, str) or not ACTOR_PATTERN.fullmatch(expected_actor):
        raise LedgerError("The authorized cross-repository dispatch actor is missing or malformed.")
    if not isinstance(source_actor, str) or not ACTOR_PATTERN.fullmatch(source_actor):
        raise LedgerError("The authorized source operator is missing or malformed.")
    if source_actor != state.get("operator"):
        raise LedgerError("The dispatch authorization source operator does not match the lifecycle session.")
    if actor != expected_actor:
        raise LedgerError("The GitHub actor does not match the authorized cross-repository dispatch actor.")
    return actor


def _require_main_branch() -> None:
    if os.environ.get("GITHUB_REF", "") != "refs/heads/main":
        raise LedgerError("Lifecycle authorization is allowed only from refs/heads/main.")


def _run_identity() -> tuple[str, int]:
    run_id = _required_environment("GITHUB_RUN_ID")
    raw_attempt = _required_environment("GITHUB_RUN_ATTEMPT")
    if not RUN_ID_PATTERN.fullmatch(run_id) or not re.fullmatch(r"[1-9][0-9]*", raw_attempt):
        raise LedgerError("The GitHub run identity is malformed.")
    return run_id, int(raw_attempt)


def _require_safe_retry_context(
    *,
    stage: str,
    session_mode: str,
    session_scope: str,
    run_id: str,
    source_run_id: str,
) -> None:
    if (
        stage != "hml"
        or session_mode != "hml"
        or session_scope != "infrastructure-only"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_WORKFLOW") != "HML infrastructure-only start"
    ):
        raise LedgerError("Safe retry ownership handoff is limited to the guarded HML infrastructure-only start.")
    if not RUN_ID_PATTERN.fullmatch(source_run_id) or source_run_id == run_id:
        raise LedgerError("The verified prior opening run ID is invalid for ownership handoff.")


def _handoff_failed_opening(
    *,
    session_id: str,
    stage: str,
    started_at: str,
    session_mode: str,
    session_scope: str,
    actor: str,
    run_id: str,
    run_attempt: int,
    source_run_id: str,
    expires_at: int,
    now: int,
) -> None:
    existing = _get_item(session_id, "STATE", consistent=True)
    try:
        previous_attempt = int(existing.get("start_run_attempt", 0))
        existing_expires_at = int(existing.get("expires_at", 0))
    except (TypeError, ValueError) as error:
        raise LedgerError("The existing lifecycle owner record is malformed; handoff fails closed.") from error
    closed_at = existing.get("closed_at")
    close_ownership_fields = (
        "close_run_id",
        "close_actor",
        "close_run_attempt",
        "close_lease_expires_at",
        "close_started_at",
        "close_attempts",
    )
    reopen_unclaimed_closed_session = (
        existing.get("status") == "closed"
        and type(closed_at) is int
        and 0 < closed_at <= now
        and not any(field in existing for field in close_ownership_fields)
    )
    if (
        (existing.get("status") != "active" and not reopen_unclaimed_closed_session)
        or existing.get("operator") != actor
        or existing.get("start_run_id") != source_run_id
        or previous_attempt < 1
        or existing.get("started_at") != started_at
        or existing.get("stage") != stage
        or existing.get("session_mode") != session_mode
        or _session_scope(existing) != session_scope
        or existing_expires_at != expires_at
        or existing_expires_at <= now
    ):
        raise LedgerError("The existing active session does not match the verified failed opening run.")

    condition = (
        "#operator = :actor AND #stage = :stage AND #mode = :mode AND #scope = :scope AND "
        "start_run_id = :source_run AND start_run_attempt = :source_attempt AND "
        "started_at = :started AND expires_at = :expires AND expires_at > :now"
    )
    update_expression = (
        "SET start_run_id = :new_run, start_run_attempt = :attempt, "
        "retry_handoff_from_run_id = :source_run, retry_handoff_at = :now"
    )
    expression_values = {
        ":new_run": _s(run_id),
        ":attempt": _n(run_attempt),
        ":source_run": _s(source_run_id),
        ":source_attempt": _n(previous_attempt),
        ":actor": _s(actor),
        ":stage": _s(stage),
        ":mode": _s(session_mode),
        ":scope": _s(session_scope),
        ":started": _s(started_at),
        ":expires": _n(expires_at),
        ":now": _n(now),
    }
    if reopen_unclaimed_closed_session:
        condition = (
            "#status = :closed AND closed_at = :closed_at AND "
            "attribute_not_exists(close_run_id) AND attribute_not_exists(close_actor) AND "
            "attribute_not_exists(close_run_attempt) AND attribute_not_exists(close_lease_expires_at) AND "
            "attribute_not_exists(close_started_at) AND attribute_not_exists(close_attempts) AND "
            + condition
        )
        update_expression = f"SET #status = :active, {update_expression} REMOVE closed_at"
        expression_values[":closed"] = _s("closed")
        expression_values[":active"] = _s("active")
        expression_values[":closed_at"] = _n(closed_at)
    else:
        condition = "#status = :active AND " + condition
        expression_values[":active"] = _s("active")

    _ddb(
        "update-item",
        {
            "Key": _key(session_id, "STATE"),
            "UpdateExpression": update_expression,
            "ConditionExpression": condition,
            "ExpressionAttributeNames": {
                "#status": "status",
                "#operator": "operator",
                "#stage": "stage",
                "#mode": "session_mode",
                "#scope": "session_scope",
            },
            "ExpressionAttributeValues": expression_values,
        },
    )


def authorize_open(
    session_id: str,
    stage: str,
    started_at: str,
    session_mode: str,
    *,
    session_scope: str = "integrated",
    safe_retry_source_run_id: str = "",
) -> None:
    _require_main_branch()
    actor = _operator()
    run_id, run_attempt = _run_identity()
    started, local_end, expires_at, ttl = _session_values(session_id, stage, started_at)
    now = int(time.time())
    if now < int(started.timestamp()) or now >= expires_at:
        raise LedgerError("The opening request is outside its authorized session window.")
    expected_mode = "hml" if stage == "hml" else "prd-window"
    if session_mode != expected_mode:
        raise LedgerError("The session mode does not match its stage.")
    if session_scope not in SESSION_SCOPES:
        raise LedgerError("The requested session scope is invalid.")
    if stage != "hml" and session_scope != "integrated":
        raise LedgerError("The limited session scopes are HML-only.")
    if safe_retry_source_run_id:
        _require_safe_retry_context(
            stage=stage,
            session_mode=session_mode,
            session_scope=session_scope,
            run_id=run_id,
            source_run_id=safe_retry_source_run_id,
        )
        current_owner = _get_item(session_id, "STATE", consistent=True)
        if current_owner.get("start_run_id") == run_id:
            try:
                current_owner_expires_at = int(current_owner.get("expires_at", 0))
            except (TypeError, ValueError) as error:
                raise LedgerError("The current lifecycle owner record is malformed; retry fails closed.") from error
            if (
                current_owner.get("status") != "active"
                or current_owner.get("operator") != actor
                or current_owner.get("started_at") != started_at
                or current_owner.get("stage") != stage
                or current_owner.get("session_mode") != session_mode
                or _session_scope(current_owner) != session_scope
                or current_owner_expires_at != expires_at
                or current_owner_expires_at <= now
            ):
                raise LedgerError("The active session owned by this run does not match the verified retry.")
        else:
            _handoff_failed_opening(
                session_id=session_id,
                stage=stage,
                started_at=started_at,
                session_mode=session_mode,
                session_scope=session_scope,
                actor=actor,
                run_id=run_id,
                run_attempt=run_attempt,
                source_run_id=safe_retry_source_run_id,
                expires_at=expires_at,
                now=now,
            )
            print(
                f"Transferred lifecycle session {session_id} from verified failed run "
                f"{safe_retry_source_run_id} to trusted run {run_id}."
            )
            return
    try:
        _ddb(
            "put-item",
            {
                "Item": {
                    **_key(session_id, "STATE"),
                    "record_type": _s("state"),
                    "stage": _s(stage),
                    "session_mode": _s(session_mode),
                    "session_scope": _s(session_scope),
                    "status": _s("active"),
                    "started_at": _s(started_at),
                    "operator": _s(actor),
                    "start_run_id": _s(run_id),
                    "start_run_attempt": _n(run_attempt),
                    "expires_at": _n(expires_at),
                    "cleanup_deadline_at": _n(
                        int(datetime.combine(started.astimezone(BRT).date(), datetime.strptime("23:00", "%H:%M").time(), tzinfo=BRT).timestamp())
                    ),
                    "ttl_epoch_seconds": _n(ttl),
                },
                "ConditionExpression": "attribute_not_exists(session_id)",
            },
        )
    except LedgerConflict:
        existing = _get_item(session_id, "STATE")
        if (
            existing.get("status") != "active"
            or existing.get("operator") != actor
            or existing.get("start_run_id") != run_id
            or existing.get("started_at") != started_at
            or existing.get("stage") != stage
            or _session_scope(existing) != session_scope
            or int(existing.get("expires_at", 0)) <= now
        ):
            raise LedgerError("A different or expired opening already owns this session ID.")
        if int(existing.get("start_run_attempt", 0)) != run_attempt:
            _ddb(
                "update-item",
                {
                    "Key": _key(session_id, "STATE"),
                    "UpdateExpression": "SET start_run_attempt = :attempt",
                    "ConditionExpression": (
                        "#status = :active AND start_run_id = :run AND "
                        "#operator = :actor AND started_at = :started AND expires_at > :now"
                    ),
                    "ExpressionAttributeNames": {"#status": "status", "#operator": "operator"},
                    "ExpressionAttributeValues": {
                        ":attempt": _n(run_attempt),
                        ":active": _s("active"),
                        ":run": _s(run_id),
                        ":actor": _s(actor),
                        ":started": _s(started_at),
                        ":now": _n(now),
                    },
                },
            )
    print(f"Authorized {stage} session {session_id} for trusted operator {actor}; expires at {local_end.isoformat()}.")


def resolve_session_scope(
    session_id: str,
    stage: str,
    started_at: str,
    *,
    dispatch_id: str = "",
) -> str:
    _require_main_branch()
    _session_values(session_id, stage, started_at)
    run_id, run_attempt = _run_identity()
    state = _get_item(session_id, "STATE", consistent=True)
    if state.get("started_at") != started_at or state.get("stage") != stage:
        raise LedgerError("The requested session does not match the lifecycle ledger.")
    scope = _session_scope(state)

    if dispatch_id:
        authorization = _get_item(session_id, f"AUTH#DISPATCH#{dispatch_id}", consistent=True)
        actor = _validate_dispatch_actor(authorization, state)
        if (
            authorization.get("status") != "consumed"
            or authorization.get("consumer_actor") != actor
            or authorization.get("consumer_run_id") != run_id
            or int(authorization.get("consumer_run_attempt", 0)) != run_attempt
            or authorization.get("target_repository") != os.environ.get("GITHUB_REPOSITORY")
            or authorization.get("target_workflow") != os.environ.get("GITHUB_WORKFLOW")
            or authorization.get("target_ref") != os.environ.get("GITHUB_REF")
            or authorization.get("action") not in {"close", "cleanup-close"}
        ):
            raise LedgerError("The close dispatch was not consumed by this exact stop run.")
    else:
        actor = _operator(allow_scheduled_stop=True)
        if (
            os.environ.get("GITHUB_EVENT_NAME") != "schedule"
            and actor not in {state.get("operator"), state.get("close_actor")}
        ):
            raise LedgerError("The session scope may be resolved only by its trusted lifecycle operator.")
    return scope


def issue_dispatch_authorization(
    *,
    session_id: str,
    dispatch_id: str,
    action: str,
    repository: str,
    workflow: str,
    ref: str,
    inputs: dict[str, str],
) -> None:
    _require_main_branch()
    dispatch_actor = _configured_dispatch_actor()
    if not SESSION_PATTERN.fullmatch(session_id):
        raise LedgerError("The lifecycle session identifier is malformed.")
    if not DISPATCH_ID_PATTERN.fullmatch(dispatch_id):
        raise LedgerError("The lifecycle dispatch identifier is malformed.")
    if action not in {"open", "health", "close", "cleanup-close", "audit"}:
        raise LedgerError("The lifecycle dispatch action is not allowed.")
    run_id, run_attempt = _run_identity()
    state = _get_item(session_id, "STATE")
    now = int(time.time())
    target_ref = _canonical_github_ref(ref)
    if state.get("stage") != session_id.split("-", 1)[0]:
        raise LedgerError("The lifecycle ledger stage does not match the session ID.")
    if (
        inputs.get("session_id") != session_id
        or inputs.get("lifecycle_dispatch_id") != dispatch_id
        or inputs.get("started_at") != state.get("started_at")
        or inputs.get("session_mode") != state.get("session_mode")
    ):
        raise LedgerError("The dispatch inputs do not bind the exact session, start, mode, and locator.")
    app_hml_dispatch = (
        action == "open"
        and state.get("stage") == "hml"
        and repository == os.environ.get("GITHUB_REPOSITORY")
        and workflow.lower() == "cd-staging.yml"
    )
    _validate_dispatch_scope(state, inputs, required=app_hml_dispatch)
    if action in {"open", "health"}:
        if (
            state.get("status") != "active"
            or state.get("operator") != _operator()
            or state.get("start_run_id") != run_id
            or int(state.get("start_run_attempt", 0)) != run_attempt
            or int(state.get("expires_at", 0)) <= now
        ):
            raise LedgerError("Only the active opening run can authorize this dispatch.")
        ttl = int(state.get("ttl_epoch_seconds", now + AUDIT_RETENTION_SECONDS))
    elif action == "close":
        valid_start_close = (
            state.get("status") == "active"
            and state.get("operator") == _operator()
            and state.get("start_run_id") == run_id
        )
        valid_stop_close = (
            state.get("status") == "closing"
            and state.get("close_actor") == state.get("operator")
            and state.get("close_run_id") == run_id
        )
        if not (valid_start_close or valid_stop_close):
            raise LedgerError("Only the authorized opening/closing run can authorize this close dispatch.")
        ttl = int(state.get("ttl_epoch_seconds", now + AUDIT_RETENTION_SECONDS))
    elif action == "cleanup-close":
        if (
            os.environ.get("GITHUB_EVENT_NAME") != "schedule"
            or os.environ.get("GITHUB_WORKFLOW") != "Expired HML lifecycle cleanup"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or int(state.get("expires_at", 0)) > now
            or state.get("status") not in {"active", "closing"}
        ):
            raise LedgerError("Only the exact scheduled cleanup workflow may authorize an expired close.")
        ttl = int(state.get("ttl_epoch_seconds", now + AUDIT_RETENTION_SECONDS))
    else:
        if (
            state.get("status") != "closing"
            or state.get("close_actor") != state.get("operator")
            or state.get("close_run_id") != run_id
        ):
            raise LedgerError("Only the active closing run can authorize the orphan audit.")
        ttl = int(state.get("ttl_epoch_seconds", now + AUDIT_RETENTION_SECONDS))
    dispatch_inputs_hash = _canonical_input_hash(inputs)
    auth_key = f"AUTH#DISPATCH#{dispatch_id}"
    authorization_expires_at = now + AUTH_TTL_SECONDS
    item = {
        **_key(session_id, auth_key),
        "record_type": _s("authorization"),
        "action": _s(action),
        "status": _s("issued"),
        "source_actor": _s(state["operator"]),
        "dispatch_actor": _s(dispatch_actor),
        "source_run_id": _s(run_id),
        "source_run_attempt": _n(run_attempt),
        "source_workflow": _s(os.environ.get("GITHUB_WORKFLOW", "")),
        "source_ref": _s(os.environ.get("GITHUB_REF", "")),
        "stage": _s(state["stage"]),
        "target_repository": _s(repository),
        "target_workflow": _s(workflow),
        "target_ref": _s(target_ref),
        "inputs_sha256": _s(dispatch_inputs_hash),
        "expires_at": _n(authorization_expires_at),
        "ttl_epoch_seconds": _n(ttl),
    }
    try:
        _ddb("put-item", {"Item": item, "ConditionExpression": "attribute_not_exists(session_id)"})
    except LedgerConflict:
        existing = _get_item(session_id, auth_key)
        if (
            existing.get("status") != "issued"
            or existing.get("source_actor") != state.get("operator")
            or existing.get("dispatch_actor") != dispatch_actor
            or existing.get("source_run_id") != run_id
            or int(existing.get("source_run_attempt", 0)) != run_attempt
            or existing.get("target_repository") != repository
            or existing.get("target_workflow") != workflow
            or existing.get("target_ref") != target_ref
            or existing.get("inputs_sha256") != dispatch_inputs_hash
            or existing.get("action") != action
            or existing.get("stage") != state.get("stage")
            or int(existing.get("expires_at", 0)) <= now
        ):
            raise LedgerError("A conflicting or consumed dispatch authorization already exists.")


def consume_dispatch_authorization(
    *,
    session_id: str,
    dispatch_id: str,
    repository: str,
    workflow: str,
    ref: str,
    inputs: dict[str, str],
    expected_action: str,
) -> str:
    if not DISPATCH_ID_PATTERN.fullmatch(dispatch_id):
        raise LedgerError("A valid lifecycle dispatch ID is required; authorization fails closed.")
    if expected_action not in {"open", "health", "close", "cleanup-close", "audit", "stop"}:
        raise LedgerError("The expected lifecycle action is invalid.")
    run_id, run_attempt = _run_identity()
    if (
        os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REPOSITORY") != repository
        or os.environ.get("GITHUB_WORKFLOW") != workflow
        or os.environ.get("GITHUB_REF") != ref
        or inputs.get("session_id") != session_id
        or inputs.get("lifecycle_dispatch_id") != dispatch_id
    ):
        raise LedgerError("The consumer repository, workflow, ref, and dispatch inputs do not match authorization.")
    auth_key = f"AUTH#DISPATCH#{dispatch_id}"
    now = int(time.time())
    hash_value = _canonical_input_hash(inputs)
    authorization = _get_item(session_id, auth_key)
    action = authorization.get("action", "")
    if expected_action == "stop":
        if action not in {"close", "cleanup-close"}:
            raise LedgerError("A stop consumer accepts only close or expired-cleanup authorization.")
    elif action != expected_action:
        raise LedgerError("The dispatch action does not match the consumer's expected action.")
    state = _get_item(session_id, "STATE")
    app_hml_consumer = (
        expected_action == "open"
        and state.get("stage") == "hml"
        and repository == os.environ.get("GITHUB_REPOSITORY")
        and os.environ.get("GITHUB_WORKFLOW", "").lower() == "cd staging"
    )
    session_scope = _validate_dispatch_scope(state, inputs, required=app_hml_consumer)
    actor = _validate_dispatch_actor(authorization, state)
    if authorization.get("record_type") != "authorization" or authorization.get("stage") != state.get("stage"):
        raise LedgerError("The dispatch authorization is not bound to the session stage.")
    if authorization.get("source_actor") != state.get("operator") or authorization.get("source_ref") != "refs/heads/main":
        raise LedgerError("The dispatch authorization source does not match the trusted lifecycle operator and branch.")

    source_run_id = authorization.get("source_run_id")
    source_run_attempt = int(authorization.get("source_run_attempt", 0))
    source_workflow = authorization.get("source_workflow")
    if action in {"open", "health"}:
        source_is_current_open = (
            source_workflow == "Coordinated environment start"
            and source_run_id == state.get("start_run_id")
            and source_run_attempt == int(state.get("start_run_attempt", 0))
            and state.get("status") == "active"
            and int(state.get("expires_at", 0)) > now
        )
        if not source_is_current_open:
            raise LedgerError("The dispatch was not issued by the active session-opening run.")
    elif action == "close":
        source_is_current_open = (
            source_workflow == "Coordinated environment start"
            and source_run_id == state.get("start_run_id")
            and source_run_attempt == int(state.get("start_run_attempt", 0))
        )
        source_is_current_close = (
            source_workflow == "Coordinated environment stop"
            and source_run_id == state.get("close_run_id")
            and source_run_attempt == int(state.get("close_run_attempt", 0))
        )
        if not (source_is_current_open or source_is_current_close) or state.get("status") not in {"active", "closing"}:
            raise LedgerError("The close dispatch was not issued by the active opening or closing run.")
    elif action == "cleanup-close":
        if (
            source_workflow != "Expired HML lifecycle cleanup"
            or state.get("status") not in {"active", "closing"}
            or int(state.get("expires_at", 0)) > now
            or source_run_attempt < 1
        ):
            raise LedgerError("The expired close dispatch was not issued by the scheduled cleanup workflow.")
    elif action == "audit":
        if (
            source_workflow != "Coordinated environment stop"
            or state.get("status") != "closing"
            or source_run_id != state.get("close_run_id")
            or source_run_attempt != int(state.get("close_run_attempt", 0))
        ):
            raise LedgerError("The audit dispatch was not issued by the active closing run.")
    try:
        _ddb(
            "update-item",
            {
                "Key": _key(session_id, auth_key),
                "UpdateExpression": "SET #status = :consumed, consumer_actor = :actor, consumer_run_id = :run, consumer_run_attempt = :attempt, consumed_at = :now",
                "ConditionExpression": "#status = :issued AND expires_at > :now AND action = :action AND stage = :stage AND target_repository = :repository AND target_workflow = :workflow AND target_ref = :ref AND inputs_sha256 = :inputs_hash AND dispatch_actor = :dispatch_actor",
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {
                    ":consumed": _s("consumed"),
                    ":actor": _s(actor),
                    ":dispatch_actor": _s(actor),
                    ":issued": _s("issued"),
                    ":action": _s(action),
                    ":stage": _s(session_id.split("-", 1)[0]),
                    ":run": _s(run_id),
                    ":attempt": _n(run_attempt),
                    ":now": _n(now),
                    ":repository": _s(repository),
                    ":workflow": _s(workflow),
                    ":ref": _s(ref),
                    ":inputs_hash": _s(hash_value),
                },
            },
        )
        return session_scope
    except LedgerConflict:
        existing = _get_item(session_id, auth_key)
        if (
            existing.get("status") == "consumed"
            and existing.get("consumer_actor") == actor
            and existing.get("consumer_run_id") == run_id
            and existing.get("target_repository") == repository
            and existing.get("target_workflow") == workflow
            and existing.get("target_ref") == ref
            and existing.get("inputs_sha256") == hash_value
            and existing.get("action") == action
            and existing.get("stage") == session_id.split("-", 1)[0]
        ):
            previous_attempt = int(existing.get("consumer_run_attempt", 0))
            if previous_attempt == run_attempt:
                return session_scope
            if previous_attempt < run_attempt and int(existing.get("expires_at", 0)) > now:
                _ddb(
                    "update-item",
                    {
                        "Key": _key(session_id, auth_key),
                        "UpdateExpression": "SET consumer_actor = :actor, consumer_run_attempt = :attempt, consumed_at = :now",
                        "ConditionExpression": "#status = :consumed AND consumer_run_id = :run AND consumer_run_attempt = :previous AND action = :action AND stage = :stage AND target_repository = :repository AND target_workflow = :workflow AND target_ref = :ref AND inputs_sha256 = :inputs_hash AND dispatch_actor = :dispatch_actor",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":attempt": _n(run_attempt),
                            ":actor": _s(actor),
                            ":dispatch_actor": _s(actor),
                            ":consumed": _s("consumed"),
                            ":run": _s(run_id),
                            ":previous": _n(previous_attempt),
                            ":action": _s(action),
                            ":stage": _s(session_id.split("-", 1)[0]),
                            ":repository": _s(repository),
                            ":workflow": _s(workflow),
                            ":ref": _s(ref),
                            ":inputs_hash": _s(hash_value),
                            ":now": _n(now),
                        },
                    },
                )
                return session_scope
        raise LedgerError("The one-use dispatch authorization is invalid, expired, or already consumed.")


def begin_close(
    session_id: str,
    stage: str,
    started_at: str,
    *,
    dispatch_id: str,
) -> None:
    _require_main_branch()
    actor = _required_environment("GITHUB_ACTOR")
    if not ACTOR_PATTERN.fullmatch(actor):
        raise LedgerError("The GitHub actor is malformed.")
    run_id, run_attempt = _run_identity()
    _, local_end, expires_at, _ = _session_values(session_id, stage, started_at)
    now = int(time.time())
    state = _get_item(session_id, "STATE")
    if state.get("started_at") != started_at or state.get("stage") != stage:
        raise LedgerError("The close request does not match the stored lifecycle session.")
    authorization: dict[str, Any] | None = None
    cleanup_authorized = False
    if dispatch_id:
        authorization = _get_item(session_id, f"AUTH#DISPATCH#{dispatch_id}")
        if (
            authorization.get("status") != "consumed"
            or authorization.get("consumer_run_id") != run_id
            or int(authorization.get("consumer_run_attempt", 0)) != run_attempt
            or authorization.get("target_repository") != os.environ.get("GITHUB_REPOSITORY")
            or authorization.get("target_workflow") != os.environ.get("GITHUB_WORKFLOW")
            or authorization.get("target_ref") != os.environ.get("GITHUB_REF")
            or authorization.get("stage") != stage
            or authorization.get("action") not in {"close", "cleanup-close"}
        ):
            raise LedgerError("The close dispatch was not claimed by this exact stop run.")
        actor = _validate_dispatch_actor(authorization, state)
        if authorization.get("consumer_actor") != actor:
            raise LedgerError("The stop dispatch was not consumed by its authorized cross-repository actor.")
        if authorization.get("action") == "close":
            if authorization.get("source_actor") != state.get("operator") or authorization.get("source_run_id") not in {
                state.get("start_run_id"),
                state.get("close_run_id"),
            }:
                raise LedgerError("The close authorization does not match the trusted opening or closing run.")
        else:
            if (
                authorization.get("source_workflow") != "Expired HML lifecycle cleanup"
                or int(authorization.get("expires_at", 0)) <= now
                or state.get("status") not in {"active", "closing"}
                or now < expires_at
            ):
                raise LedgerError("Expired cleanup authorization is missing, expired, or from another workflow.")
            cleanup_authorized = True
    elif os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        actor = _operator()
        if actor not in {state.get("operator"), state.get("close_actor")}:
            raise LedgerError("A manual close requires the trusted lifecycle operator.")
    elif os.environ.get("GITHUB_EVENT_NAME") == "schedule":
        actor = _operator(allow_scheduled_stop=True)
        if now < expires_at:
            raise LedgerError("The scheduled stop cannot close a session before its maximum window expires.")
    else:
        raise LedgerError("Close requires a trusted operator, an issued authorization, or the exact scheduled stop workflow.")

    cleanup_deadline = int(state.get("cleanup_deadline_at", 0))
    if now >= cleanup_deadline and not cleanup_authorized:
        raise LedgerError("Same-day teardown window expired; only the daily cleanup workflow may continue it.")

    close_lease_expires_at = (
        now + CLOSE_LEASE_SECONDS
        if cleanup_authorized
        else min(now + CLOSE_LEASE_SECONDS, cleanup_deadline)
    )
    if close_lease_expires_at <= now:
        raise LedgerError("No safe teardown lease remains; wait for the scheduled expired-session cleanup.")
    if cleanup_authorized:
        condition_expression = "(#status = :active AND expires_at <= :now) OR (#status = :closing AND close_lease_expires_at <= :now AND expires_at <= :now)"
    else:
        condition_expression = "#status = :active OR (#status = :closing AND ((close_run_id = :run AND close_actor = :actor) OR (close_lease_expires_at <= :now AND close_actor = :actor)))"
    try:
        _ddb(
            "update-item",
            {
                "Key": _key(session_id, "STATE"),
                "UpdateExpression": "SET #status = :closing, close_actor = :actor, close_run_id = :run, close_run_attempt = :attempt, close_lease_expires_at = :lease, close_started_at = if_not_exists(close_started_at, :now), close_attempts = if_not_exists(close_attempts, :zero) + :one",
                "ConditionExpression": condition_expression,
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {
                    ":closing": _s("closing"),
                    ":active": _s("active"),
                    ":actor": _s(state.get("operator", actor)),
                    ":run": _s(run_id),
                    ":attempt": _n(run_attempt),
                    ":lease": _n(close_lease_expires_at),
                    ":zero": _n(0),
                    ":one": _n(1),
                    ":now": _n(now),
                },
            },
        )
    except LedgerConflict:
        existing = _get_item(session_id, "STATE")
        if (
            existing.get("status") == "closing"
            and existing.get("close_actor") == state.get("operator")
            and existing.get("close_run_id") == run_id
            and int(existing.get("close_lease_expires_at", 0)) > now
        ):
            return
        raise LedgerError("Another close owns this session or the session is already closed.")
    print(f"Claimed teardown for {session_id}; session ended at {local_end.isoformat()}.")


def finalize_close(session_id: str) -> None:
    _operator(allow_scheduled_stop=True)
    run_id, run_attempt = _run_identity()
    now = int(time.time())
    _ddb(
        "update-item",
        {
            "Key": _key(session_id, "STATE"),
            "UpdateExpression": "SET #status = :closed, closed_at = :now REMOVE close_lease_expires_at",
            "ConditionExpression": "#status = :closing AND close_run_id = :run AND close_run_attempt = :attempt",
            "ExpressionAttributeNames": {"#status": "status"},
            "ExpressionAttributeValues": {
                ":closed": _s("closed"),
                ":closing": _s("closing"),
                ":now": _n(now),
                ":run": _s(run_id),
                ":attempt": _n(run_attempt),
            },
        },
    )


def record_close_step(session_id: str, step: str, outcome: str, detail: str) -> None:
    _operator(allow_scheduled_stop=True)
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", step):
        raise LedgerError("The teardown step name is malformed.")
    if outcome not in {"success", "failure", "skipped"}:
        raise LedgerError("The teardown step outcome is invalid.")
    run_id, run_attempt = _run_identity()
    result = {
        "outcome": _s(outcome),
        "detail": _s(detail[:400]),
        "run_id": _s(run_id),
        "run_attempt": _n(run_attempt),
        "recorded_at": _n(int(time.time())),
    }
    _ddb(
        "update-item",
        {
            "Key": _key(session_id, "STATE"),
            "UpdateExpression": "SET #step = :result",
            "ConditionExpression": "#status = :closing AND close_run_id = :run AND close_run_attempt = :attempt",
            "ExpressionAttributeNames": {"#step": f"step_{step}", "#status": "status"},
            "ExpressionAttributeValues": {
                ":result": {"M": result},
                ":closing": _s("closing"),
                ":run": _s(run_id),
                ":attempt": _n(run_attempt),
            },
        },
    )


def find_expired_sessions(*, limit: int = 100) -> list[dict[str, Any]]:
    now = int(time.time())
    sessions: list[dict[str, Any]] = []
    for status in ("active", "closing"):
        exclusive_start_key: dict[str, Any] | None = None
        while len(sessions) < limit:
            request: dict[str, Any] = {
                "IndexName": GSI_NAME,
                "KeyConditionExpression": "#status = :status AND expires_at <= :now",
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {":status": _s(status), ":now": _n(now)},
                "Limit": min(limit - len(sessions), 100),
                "ScanIndexForward": True,
            }
            if exclusive_start_key:
                request["ExclusiveStartKey"] = exclusive_start_key
            response = _ddb("query", request, paginate=False)
            for item in response.get("Items", []):
                decoded = _decode_item(item)
                if decoded.get("record_key") != "STATE" or decoded.get("record_type") != "state":
                    continue
                if status == "closing" and int(decoded.get("close_lease_expires_at", 0)) > now:
                    continue
                sessions.append(decoded)
            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break
    return sorted(sessions, key=lambda item: int(item.get("expires_at", 0)))[:limit]


def _inputs_from_event() -> dict[str, str]:
    event_path = _required_environment("GITHUB_EVENT_PATH")
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LedgerError("The GitHub dispatch event could not be read; authorization fails closed.") from error
    inputs = event.get("inputs") if isinstance(event, dict) else None
    if not isinstance(inputs, dict):
        raise LedgerError("The GitHub event has no dispatch inputs; authorization fails closed.")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in inputs.items()):
        raise LedgerError("The GitHub dispatch inputs are malformed; authorization fails closed.")
    return inputs


def _append_github_output(output_path: str, name: str, value: str) -> None:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,39}", name) or "\n" in value or "\r" in value:
        raise LedgerError("The lifecycle workflow output is malformed.")
    with Path(output_path).open("a", encoding="utf-8") as output_file:
        output_file.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    open_parser = subparsers.add_parser("authorize-open")
    open_parser.add_argument("--session-id", required=True)
    open_parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    open_parser.add_argument("--started-at", required=True)
    open_parser.add_argument("--session-mode", required=True)
    open_parser.add_argument("--session-scope", choices=tuple(sorted(SESSION_SCOPES)), default="integrated")
    open_parser.add_argument("--safe-retry-source-run-id", default="")

    dispatch_parser = subparsers.add_parser("consume-dispatch")
    dispatch_parser.add_argument("--session-id", required=True)
    dispatch_parser.add_argument("--dispatch-id", required=True)
    dispatch_parser.add_argument("--repository", required=True)
    dispatch_parser.add_argument("--workflow", required=True)
    dispatch_parser.add_argument("--ref", required=True)
    dispatch_parser.add_argument(
        "--expected-action",
        choices=("open", "health", "close", "cleanup-close", "audit", "stop"),
        required=True,
    )
    dispatch_parser.add_argument("--github-output", default="")

    scope_parser = subparsers.add_parser("resolve-session-scope")
    scope_parser.add_argument("--session-id", required=True)
    scope_parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    scope_parser.add_argument("--started-at", required=True)
    scope_parser.add_argument("--dispatch-id", default="")
    scope_parser.add_argument("--github-output", required=True)

    close_parser = subparsers.add_parser("begin-close")
    close_parser.add_argument("--session-id", required=True)
    close_parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    close_parser.add_argument("--started-at", required=True)
    close_parser.add_argument("--dispatch-id", default="")

    close_step_parser = subparsers.add_parser("record-close-step")
    close_step_parser.add_argument("--session-id", required=True)
    close_step_parser.add_argument("--step", required=True)
    close_step_parser.add_argument("--outcome", choices=("success", "failure", "skipped"), required=True)
    close_step_parser.add_argument("--detail", default="")

    finalize_parser = subparsers.add_parser("finalize-close")
    finalize_parser.add_argument("--session-id", required=True)

    expired_parser = subparsers.add_parser("list-expired")
    expired_parser.add_argument("--output", required=True)
    expired_parser.add_argument("--limit", type=int, default=100)

    arguments = parser.parse_args()
    try:
        if arguments.command == "authorize-open":
            authorize_open(
                arguments.session_id,
                arguments.stage,
                arguments.started_at,
                arguments.session_mode,
                session_scope=arguments.session_scope,
                safe_retry_source_run_id=arguments.safe_retry_source_run_id,
            )
        elif arguments.command == "consume-dispatch":
            session_scope = consume_dispatch_authorization(
                session_id=arguments.session_id,
                dispatch_id=arguments.dispatch_id,
                repository=arguments.repository,
                workflow=arguments.workflow,
                ref=arguments.ref,
                inputs=_inputs_from_event(),
                expected_action=arguments.expected_action,
            )
            if arguments.github_output:
                _append_github_output(arguments.github_output, "session_scope", session_scope)
        elif arguments.command == "resolve-session-scope":
            session_scope = resolve_session_scope(
                arguments.session_id,
                arguments.stage,
                arguments.started_at,
                dispatch_id=arguments.dispatch_id,
            )
            _append_github_output(arguments.github_output, "session_scope", session_scope)
        elif arguments.command == "begin-close":
            begin_close(
                arguments.session_id,
                arguments.stage,
                arguments.started_at,
                dispatch_id=arguments.dispatch_id,
            )
        elif arguments.command == "finalize-close":
            finalize_close(arguments.session_id)
        elif arguments.command == "record-close-step":
            record_close_step(arguments.session_id, arguments.step, arguments.outcome, arguments.detail)
        elif arguments.command == "list-expired":
            if arguments.limit < 1 or arguments.limit > 100:
                raise LedgerError("The cleanup batch limit must be between 1 and 100.")
            expired = find_expired_sessions(limit=arguments.limit)
            output_path = Path(arguments.output)
            output_path.write_text(json.dumps(expired, indent=2) + "\n", encoding="utf-8")
            print(f"Found {len(expired)} expired lifecycle session(s).")
        return 0
    except LedgerError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
