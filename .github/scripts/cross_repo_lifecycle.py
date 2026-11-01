#!/usr/bin/env python3
"""Dispatch and wait for one precisely correlated GitHub Actions workflow run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WORKFLOW_PATTERN = re.compile(r"^(?:[A-Za-z0-9_.-]+\.ya?ml|[0-9]+)$")
OUTPUT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
TITLE_PATTERN = re.compile(r"^[^\r\n\x00-\x1f]{1,240}$")
ACTIVE_RUN_STATUSES = {"queued", "waiting", "in_progress", "requested", "pending", "canceling"}
DISPATCH_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
SESSION_TOKEN_PATTERN = re.compile(r"^[0-9a-f]{64}$")
AUTHORIZATION_ACTIONS = {"open", "health", "close", "cleanup-close", "audit"}
MAX_CANCEL_WAIT_SECONDS = 30
MAX_API_TIMEOUT_SECONDS = 30
POST_DEADLINE_LOOKUP_SECONDS = 15
CANCEL_REQUEST_TIMEOUT_SECONDS = 10


class LifecycleDispatchError(RuntimeError):
    """Raised when a workflow cannot be safely correlated to its dispatch."""


def _utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise LifecycleDispatchError("The deadline must be an ISO-8601 UTC timestamp.") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise LifecycleDispatchError("The deadline must be an ISO-8601 UTC timestamp.")
    return parsed.astimezone(timezone.utc)


def _api_request(
    token: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_seconds: float = MAX_API_TIMEOUT_SECONDS,
) -> Any:
    if timeout_seconds <= 0:
        raise LifecycleDispatchError("The lifecycle deadline expired before a GitHub API request.")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{API_ROOT}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "auto-shop-prd-lifecycle-coordinator",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status == 204 or response.status == 202:
                return None
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise LifecycleDispatchError(
            f"GitHub API {method} request failed with HTTP {error.code}."
        ) from error
    except URLError as error:
        raise LifecycleDispatchError("GitHub API could not be reached.") from error


def _validate_arguments(arguments: argparse.Namespace) -> tuple[str, dict[str, str]]:
    if not REPOSITORY_PATTERN.fullmatch(arguments.repository):
        raise LifecycleDispatchError("Repository must use the owner/name format.")
    if not WORKFLOW_PATTERN.fullmatch(arguments.workflow):
        raise LifecycleDispatchError("Workflow must be a workflow filename or numeric ID.")
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", arguments.ref) or ".." in arguments.ref:
        raise LifecycleDispatchError("Workflow ref contains unsupported characters.")
    if not TITLE_PATTERN.fullmatch(arguments.expected_title):
        raise LifecycleDispatchError("Expected workflow title is missing or malformed.")
    if not OUTPUT_PATTERN.fullmatch(arguments.output_name):
        raise LifecycleDispatchError("Output name must be a valid GitHub Actions identifier.")
    if arguments.timeout_seconds < 1 or arguments.poll_seconds < 1:
        raise LifecycleDispatchError("Timeout and polling intervals must be positive.")
    authorization_action = getattr(arguments, "authorization_action", "")
    if authorization_action and authorization_action not in AUTHORIZATION_ACTIONS:
        raise LifecycleDispatchError("The lifecycle authorization action is not allowed.")
    if not 1 <= arguments.cancel_wait_seconds <= MAX_CANCEL_WAIT_SECONDS:
        raise LifecycleDispatchError(
            f"Post-cancellation wait must be between 1 and {MAX_CANCEL_WAIT_SECONDS} seconds."
        )
    if bool(arguments.cancel_active_workflow) != bool(arguments.cancel_title_prefix):
        raise LifecycleDispatchError(
            "Cancel-before-dispatch requires both a workflow and an exact session title prefix."
        )
    if arguments.cancel_active_workflow and not WORKFLOW_PATTERN.fullmatch(arguments.cancel_active_workflow):
        raise LifecycleDispatchError("The cancel-before-dispatch workflow name is malformed.")
    if arguments.cancel_title_prefix and not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/", arguments.cancel_title_prefix
    ):
        raise LifecycleDispatchError("The cancel-before-dispatch title prefix is malformed.")

    try:
        raw_inputs = json.loads(arguments.inputs)
    except json.JSONDecodeError as error:
        raise LifecycleDispatchError("Workflow inputs must be a JSON object.") from error
    if not isinstance(raw_inputs, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in raw_inputs.items()
    ):
        raise LifecycleDispatchError("Workflow inputs must be a JSON object containing only strings.")
    if any("\n" in value or "\r" in value for value in raw_inputs.values()):
        raise LifecycleDispatchError("Workflow inputs cannot contain line breaks.")
    if arguments.cancel_active_workflow:
        session_id = raw_inputs.get("session_id", "")
        if (
            arguments.workflow != "destroy.yml"
            or arguments.cancel_active_workflow != "apply.yml"
            or not re.fullmatch(r"(?:hml|prd)-\d{4}-\d{2}-\d{2}", session_id)
            or arguments.cancel_title_prefix != f"database/{session_id}/apply/"
        ):
            raise LifecycleDispatchError(
                "Cancel-before-destroy must target only apply.yml runs for the database session in the dispatch inputs."
            )
    return arguments.repository, raw_inputs


def _list_runs(
    token: str,
    repository: str,
    workflow: str,
    ref: str,
    created_after: datetime,
    *,
    timeout_seconds: float = MAX_API_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    created_filter = ">=" + created_after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = urlencode(
        {
            "event": "workflow_dispatch",
            "branch": ref,
            "created": created_filter,
            "per_page": "100",
        }
    )
    result = _api_request(
        token,
        "GET",
        f"/repos/{repository}/actions/workflows/{workflow}/runs?{query}",
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(result, dict) or not isinstance(result.get("workflow_runs"), list):
        raise LifecycleDispatchError("GitHub returned an invalid workflow-run response.")
    total_count = result.get("total_count")
    if not isinstance(total_count, int):
        raise LifecycleDispatchError("GitHub returned an invalid workflow-run count.")
    if total_count > 100:
        raise LifecycleDispatchError(
            "More than 100 workflow runs fall inside the correlation window; refusing an ambiguous dispatch."
        )
    if not all(isinstance(run, dict) for run in result["workflow_runs"]):
        raise LifecycleDispatchError("GitHub returned malformed workflow run entries.")
    return result["workflow_runs"]


def _correlated_runs(
    runs: list[dict[str, Any]],
    expected_title: str,
    dispatch_not_before: datetime,
    pre_dispatch_ids: set[str],
) -> list[dict[str, Any]]:
    matches = []
    for run in runs:
        if run.get("display_title") != expected_title:
            continue
        try:
            created_at = _utc_timestamp(str(run.get("created_at", "")))
        except LifecycleDispatchError:
            continue
        run_id = run.get("id")
        if created_at >= dispatch_not_before and str(run_id) not in pre_dispatch_ids:
            matches.append(run)
    return matches


def _get_run(
    token: str,
    repository: str,
    run_id: int,
    *,
    timeout_seconds: float = MAX_API_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    result = _api_request(
        token,
        "GET",
        f"/repos/{repository}/actions/runs/{run_id}",
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(result, dict) or result.get("id") != run_id:
        raise LifecycleDispatchError("GitHub returned an invalid correlated workflow run.")
    return result


def _write_completed_outputs(arguments: argparse.Namespace, run: dict[str, Any]) -> None:
    run_id = run.get("id")
    run_attempt = run.get("run_attempt")
    if not isinstance(run_id, int) or not isinstance(run_attempt, int):
        raise LifecycleDispatchError("GitHub returned an invalid run ID or attempt.")
    plan_id = f"{run_id}-{run_attempt}"
    _append_output(arguments.github_output, f"{arguments.output_name}_run_id", str(run_id))
    _append_output(
        arguments.github_output,
        f"{arguments.output_name}_dispatch_id",
        str(arguments.lifecycle_dispatch_id),
    )
    _append_output(
        arguments.github_output,
        f"{arguments.output_name}_run_attempt",
        str(run_attempt),
    )
    _append_output(arguments.github_output, f"{arguments.output_name}_plan_id", plan_id)


def _cancel_session_apply_runs(
    token: str,
    repository: str,
    workflow: str,
    ref: str,
    title_prefix: str,
    poll_seconds: int,
    deadline: datetime,
) -> None:
    while True:
        if datetime.now(timezone.utc) >= deadline:
            raise LifecycleDispatchError(
                "The lifecycle deadline expired while waiting for session apply runs; destroy was not dispatched."
            )
        runs = _list_runs(
            token,
            repository,
            workflow,
            ref,
            datetime.now(timezone.utc) - timedelta(hours=48),
            timeout_seconds=_deadline_request_timeout(deadline),
        )
        matching = [
            run
            for run in runs
            if isinstance(run.get("display_title"), str)
            and run["display_title"].startswith(title_prefix)
            and run.get("status") in ACTIVE_RUN_STATUSES
        ]
        if len(matching) > 1:
            raise LifecycleDispatchError(
                "Multiple active apply runs match the session prefix; no run was canceled and destroy was not dispatched."
            )
        if not matching:
            return

        run_id = matching[0].get("id")
        if not isinstance(run_id, int):
            raise LifecycleDispatchError(
                "The matching active apply run has no valid ID; no run was canceled."
            )
        if datetime.now(timezone.utc) >= deadline:
            raise LifecycleDispatchError(
                "The lifecycle deadline expired before canceling the session apply run; destroy was not dispatched."
            )
        cancellation_error = ""
        try:
            _api_request(
                token,
                "POST",
                f"/repos/{repository}/actions/runs/{run_id}/cancel",
                timeout_seconds=_deadline_request_timeout(deadline),
            )
        except LifecycleDispatchError as error:
            cancellation_error = str(error)
        print(f"Session apply run {run_id} is being canceled or has just completed; waiting before destroy.")

        while True:
            if datetime.now(timezone.utc) >= deadline:
                raise LifecycleDispatchError(
                    f"The lifecycle deadline expired before apply run {run_id} reached completed; destroy was not dispatched."
                )
            try:
                latest = _get_run(
                    token,
                    repository,
                    run_id,
                    timeout_seconds=_deadline_request_timeout(deadline),
                )
            except LifecycleDispatchError:
                remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
                if remaining <= 0:
                    raise LifecycleDispatchError(
                        f"The lifecycle deadline expired before apply run {run_id} reached completed; destroy was not dispatched."
                    )
                time.sleep(min(poll_seconds, remaining))
                continue
            status = latest.get("status")
            if status == "completed":
                try:
                    completed_at = _utc_timestamp(str(latest.get("completed_at", "")))
                except LifecycleDispatchError as error:
                    raise LifecycleDispatchError(
                        f"Apply run {run_id} reached completed with an invalid completion timestamp; destroy was not dispatched."
                    ) from error
                if completed_at > deadline:
                    raise LifecycleDispatchError(
                        f"Apply run {run_id} completed after the lifecycle deadline; destroy was not dispatched."
                    )
                if cancellation_error:
                    print(
                        f"Apply run {run_id} completed despite a cancellation response error: {cancellation_error}"
                    )
                break
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                raise LifecycleDispatchError(
                    f"The lifecycle deadline expired before apply run {run_id} reached completed; destroy was not dispatched."
                )
            time.sleep(min(poll_seconds, remaining))


def _wait_for_cancelled_run(
    token: str,
    repository: str,
    run_id: int,
    expected_title: str,
    cancellation_error: str,
    poll_seconds: int,
    wait_seconds: int,
) -> None:
    deadline = time.monotonic() + wait_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            latest_run = _get_run(
                token,
                repository,
                run_id,
                timeout_seconds=min(MAX_API_TIMEOUT_SECONDS, remaining),
            )
        except LifecycleDispatchError:
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(poll_seconds, remaining))
            continue

        if latest_run.get("status") == "completed":
            detail = f"run {run_id} reached completed with conclusion '{latest_run.get('conclusion')}'."
            if cancellation_error:
                detail += f" Cancellation request reported: {cancellation_error}"
            raise LifecycleDispatchError(
                f"Deadline reached before '{expected_title}' completed; {detail}"
            )

        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(poll_seconds, remaining))

    raise LifecycleDispatchError(
        f"Deadline reached before '{expected_title}' completed; cancellation was requested for run "
        f"{run_id}, but it did not reach completed within {wait_seconds} seconds and may still be active."
    )


def _append_output(path: str, name: str, value: str) -> None:
    if "\n" in value or "\r" in value:
        raise LifecycleDispatchError("GitHub workflow output contained a line break.")
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


def _issue_dispatch_authorization(
    *,
    action: str,
    session_id: str,
    dispatch_id: str,
    repository: str,
    workflow: str,
    ref: str,
    inputs: dict[str, str],
) -> None:
    command = [
        sys.executable,
        str(Path(__file__).with_name("lifecycle_session_ledger.py")),
        "issue-dispatch",
        "--session-id",
        session_id,
        "--dispatch-id",
        dispatch_id,
        "--action",
        action,
        "--repository",
        repository,
        "--workflow",
        workflow,
        "--ref",
        ref,
        "--inputs",
        json.dumps(inputs, separators=(",", ":")),
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LifecycleDispatchError(
            "The lifecycle ledger could not issue the child authorization; no child was dispatched."
        ) from error
    if result.returncode != 0:
        raise LifecycleDispatchError(
            "The lifecycle ledger rejected the exact child authorization; no child was dispatched."
        )


def _stable_dispatch_id(
    arguments: argparse.Namespace,
    repository: str,
    inputs: dict[str, str],
    *,
    run_attempt: int | None = None,
) -> str:
    workflow_run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if not workflow_run_id:
        return uuid.uuid4().hex
    if not re.fullmatch(r"[0-9]+", workflow_run_id):
        raise LifecycleDispatchError("GITHUB_RUN_ID must contain only digits.")
    if run_attempt is None:
        raw_run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip()
        if not re.fullmatch(r"[1-9][0-9]*", raw_run_attempt):
            raise LifecycleDispatchError("GITHUB_RUN_ATTEMPT must be a positive integer.")
        run_attempt = int(raw_run_attempt)
    if run_attempt < 1:
        raise LifecycleDispatchError("The central workflow attempt must be a positive integer.")

    identity = {
        "workflow_run_id": workflow_run_id,
        "workflow_run_attempt": run_attempt,
        "repository": repository,
        "workflow": arguments.workflow,
        "ref": arguments.ref,
        "expected_title": arguments.expected_title,
        "inputs": {key: value for key, value in inputs.items() if key != "session_token"},
    }
    canonical_identity = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()[:32]


def _deadline_request_timeout(deadline: datetime) -> float:
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        raise LifecycleDispatchError("The lifecycle phase deadline expired before a GitHub API request.")
    return min(MAX_API_TIMEOUT_SECONDS, remaining)


def _prior_operation_runs(
    runs: list[dict[str, Any]],
    arguments: argparse.Namespace,
    repository: str,
    inputs: dict[str, str],
    current_attempt: int,
) -> tuple[str, dict[str, Any] | None]:
    dispatch_ids = {
        _stable_dispatch_id(arguments, repository, inputs, run_attempt=attempt): attempt
        for attempt in range(1, current_attempt + 1)
    }
    title_to_id = {
        f"{arguments.expected_title}:{dispatch_id}": dispatch_id for dispatch_id in dispatch_ids
    }
    matching = [run for run in runs if run.get("display_title") in title_to_id]
    counts: dict[str, int] = {}
    for run in matching:
        title = str(run.get("display_title", ""))
        counts[title] = counts.get(title, 0) + 1
    if any(count > 1 for count in counts.values()):
        raise LifecycleDispatchError(
            "Multiple prior workflow runs matched one lifecycle attempt; refusing to guess."
        )

    active = [run for run in matching if run.get("status") in ACTIVE_RUN_STATUSES]
    successful = [
        run
        for run in matching
        if run.get("status") == "completed" and run.get("conclusion") == "success"
    ]
    unexpected = [
        run
        for run in matching
        if run.get("status") not in ACTIVE_RUN_STATUSES and run.get("status") != "completed"
    ]
    if unexpected or len(active) > 1 or len(successful) > 1 or (active and successful):
        raise LifecycleDispatchError(
            "Prior lifecycle runs are active or ambiguous; refusing to dispatch duplicate work."
        )

    if active:
        selected = active[0]
    elif successful:
        selected = successful[0]
    else:
        current_attempt_id = _stable_dispatch_id(
            arguments, repository, inputs, run_attempt=current_attempt
        )
        current_title = f"{arguments.expected_title}:{current_attempt_id}"
        current_matches = [run for run in matching if run.get("display_title") == current_title]
        if current_matches:
            selected = current_matches[0]
        else:
            return current_attempt_id, None

    selected_title = str(selected.get("display_title", ""))
    dispatch_id = title_to_id.get(selected_title)
    if dispatch_id is None:
        raise LifecycleDispatchError("The prior lifecycle run title could not be correlated to its dispatch ID.")
    return dispatch_id, selected


def dispatch_and_wait(arguments: argparse.Namespace) -> int:
    token = os.environ.get("LIFECYCLE_CROSS_REPO_TOKEN", "").strip()
    if not token:
        raise LifecycleDispatchError(
            "LIFECYCLE_CROSS_REPO_TOKEN is required; no GITHUB_TOKEN fallback is allowed."
        )

    repository, inputs = _validate_arguments(arguments)
    if getattr(arguments, "no_session_token", False):
        if "session_token" in inputs or "lifecycle_dispatch_id" in inputs:
            raise LifecycleDispatchError(
                "lifecycle_dispatch_id is injected by the coordinator and must not be supplied directly."
            )
    else:
        session_token = os.environ.get("LIFECYCLE_SESSION_TOKEN", "").strip()
        if not SESSION_TOKEN_PATTERN.fullmatch(session_token):
            raise LifecycleDispatchError(
                "LIFECYCLE_SESSION_TOKEN must be a valid coordinator-issued capability; no run was dispatched."
            )
        if "session_token" in inputs or "lifecycle_dispatch_id" in inputs:
            raise LifecycleDispatchError(
                "session_token and lifecycle_dispatch_id are injected by the coordinator and must not be supplied directly."
            )
        inputs["session_token"] = session_token
    raw_run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip()
    if not re.fullmatch(r"[1-9][0-9]*", raw_run_attempt):
        raise LifecycleDispatchError("GITHUB_RUN_ATTEMPT must be a positive integer.")
    current_attempt = int(raw_run_attempt)
    dispatch_id = _stable_dispatch_id(
        arguments, repository, inputs, run_attempt=current_attempt
    )
    if not DISPATCH_ID_PATTERN.fullmatch(dispatch_id):
        raise LifecycleDispatchError("Generated dispatch ID is malformed.")
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(seconds=arguments.timeout_seconds)
    if arguments.deadline_utc:
        requested_deadline = _utc_timestamp(arguments.deadline_utc)
        if requested_deadline <= now:
            raise LifecycleDispatchError("The lifecycle phase deadline has already passed.")
        deadline = min(deadline, requested_deadline)

    owner, repo_name = repository.split("/", 1)
    # Reuse an in-progress or successful phase from any earlier coordinator attempt.
    # A new attempt gets a new ID only when every previous matching attempt failed.
    pre_dispatch_runs = _list_runs(
        token,
        repository,
        arguments.workflow,
        arguments.ref,
        now - timedelta(hours=48),
        timeout_seconds=_deadline_request_timeout(deadline),
    )
    dispatch_id, selected_run = _prior_operation_runs(
        pre_dispatch_runs,
        arguments,
        repository,
        inputs,
        current_attempt,
    )
    expected_title = f"{arguments.expected_title}:{dispatch_id}"
    if not TITLE_PATTERN.fullmatch(expected_title):
        raise LifecycleDispatchError("Expected title plus dispatch ID exceeds GitHub's supported title length.")
    inputs["lifecycle_dispatch_id"] = dispatch_id
    arguments.lifecycle_dispatch_id = dispatch_id

    if selected_run:
        try:
            dispatch_not_before = _utc_timestamp(str(selected_run.get("created_at", "")))
        except LifecycleDispatchError as error:
            raise LifecycleDispatchError(
                "The prior correlated workflow run has an invalid creation timestamp."
            ) from error
        pre_dispatch_ids: set[str] = set()
        print(f"Resuming correlated workflow run {selected_run.get('id')} for {expected_title}.")
    else:
        pre_dispatch_ids = {
            str(run.get("id"))
            for run in pre_dispatch_runs
            if run.get("display_title") == expected_title and run.get("id") is not None
        }
        dispatch_not_before = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=2)
        dispatch_delay = (dispatch_not_before - datetime.now(timezone.utc)).total_seconds()
        if dispatch_delay > 0:
            time.sleep(dispatch_delay)
        if datetime.now(timezone.utc) >= deadline:
            raise LifecycleDispatchError("The lifecycle phase deadline passed before dispatch could start.")
        if arguments.cancel_active_workflow:
            _cancel_session_apply_runs(
                token,
                repository,
                arguments.cancel_active_workflow,
                arguments.ref,
                arguments.cancel_title_prefix,
                arguments.poll_seconds,
                deadline,
            )
        if datetime.now(timezone.utc) >= deadline:
            raise LifecycleDispatchError("The lifecycle phase deadline passed before dispatch could start.")
        authorization_action = getattr(arguments, "authorization_action", "")
        if authorization_action:
            _issue_dispatch_authorization(
                action=authorization_action,
                session_id=inputs.get("session_id", ""),
                dispatch_id=dispatch_id,
                repository=repository,
                workflow=arguments.workflow,
                ref=arguments.ref,
                inputs=inputs,
            )
        _api_request(
            token,
            "POST",
            f"/repos/{owner}/{repo_name}/actions/workflows/{arguments.workflow}/dispatches",
            {"ref": arguments.ref, "inputs": inputs},
            timeout_seconds=_deadline_request_timeout(deadline),
        )

    while datetime.now(timezone.utc) < deadline:
        runs = _list_runs(
            token,
            repository,
            arguments.workflow,
            arguments.ref,
            dispatch_not_before,
            timeout_seconds=_deadline_request_timeout(deadline),
        )
        matches = _correlated_runs(
            runs,
            expected_title,
            dispatch_not_before,
            pre_dispatch_ids,
        )

        if len(matches) > 1:
            raise LifecycleDispatchError(
                "Multiple workflow runs matched the same title and dispatch window; refusing to guess."
            )
        if matches:
            run = matches[0]
            status = run.get("status")
            if status == "completed":
                conclusion = run.get("conclusion")
                if conclusion != "success":
                    raise LifecycleDispatchError(
                        f"Correlated run {run.get('id')} ended with conclusion '{conclusion}'."
                    )
                try:
                    completed_at = _utc_timestamp(str(run.get("completed_at", "")))
                except LifecycleDispatchError as error:
                    raise LifecycleDispatchError("GitHub returned an invalid completion timestamp.") from error
                if completed_at > deadline:
                    break
                _write_completed_outputs(arguments, run)
                print(
                    f"Completed {expected_title} as run {run.get('id')} attempt {run.get('run_attempt')}."
                )
                return 0
            if status not in ACTIVE_RUN_STATUSES:
                raise LifecycleDispatchError(
                    f"Correlated run {run.get('id')} entered unexpected status '{status}'."
                )

        seconds_remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        if seconds_remaining > 0:
            time.sleep(min(arguments.poll_seconds, seconds_remaining))

    final_runs = _list_runs(
        token,
        repository,
        arguments.workflow,
        arguments.ref,
        dispatch_not_before,
        timeout_seconds=POST_DEADLINE_LOOKUP_SECONDS,
    )
    final_matches = _correlated_runs(
        final_runs,
        expected_title,
        dispatch_not_before,
        pre_dispatch_ids,
    )
    if len(final_matches) != 1:
        raise LifecycleDispatchError(
            f"Deadline reached without one unambiguous new run titled '{expected_title}'; no run was canceled."
        )

    run = final_matches[0]
    run_id = run.get("id")
    if not isinstance(run_id, int):
        raise LifecycleDispatchError("The uniquely correlated run has no valid ID; no run was canceled.")

    if run.get("status") == "completed":
        completed_at_value = run.get("completed_at")
        try:
            completed_at = _utc_timestamp(str(completed_at_value))
        except LifecycleDispatchError as error:
            raise LifecycleDispatchError(
                f"Deadline reached and correlated run {run_id} is complete, but its completion time is invalid."
            ) from error
        if run.get("conclusion") == "success" and completed_at <= deadline:
            _write_completed_outputs(arguments, run)
            print(
                f"Completed {expected_title} as run {run_id} before the deadline; result became visible afterward."
            )
            return 0
        raise LifecycleDispatchError(
            f"Deadline reached; correlated run {run_id} completed at {completed_at.isoformat()} "
            f"with conclusion '{run.get('conclusion')}'."
        )

    cancellation_error = ""
    try:
        _api_request(
            token,
            "POST",
            f"/repos/{repository}/actions/runs/{run_id}/cancel",
            timeout_seconds=CANCEL_REQUEST_TIMEOUT_SECONDS,
        )
    except LifecycleDispatchError as error:
        cancellation_error = str(error)

    print(f"Deadline reached; attempting cancellation of correlated run {run_id} and waiting for completion.")
    _wait_for_cancelled_run(
        token,
        repository,
        run_id,
        expected_title,
        cancellation_error,
        arguments.poll_seconds,
        arguments.cancel_wait_seconds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--github-output", required=True)
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--cancel-wait-seconds", type=int, default=30)
    parser.add_argument("--deadline-utc")
    parser.add_argument("--authorization-action", choices=tuple(sorted(AUTHORIZATION_ACTIONS)), default="")
    parser.add_argument("--cancel-active-workflow", default="")
    parser.add_argument("--cancel-title-prefix", default="")
    parser.add_argument("--no-session-token", action="store_true")
    arguments = parser.parse_args()

    try:
        return dispatch_and_wait(arguments)
    except (LifecycleDispatchError, OSError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
