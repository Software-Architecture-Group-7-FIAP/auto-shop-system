#!/usr/bin/env python3
"""Fail the orphan audit if any correlated remote lifecycle run is still active."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import cross_repo_lifecycle  # noqa: E402


API_LOOKUP_TIMEOUT_SECONDS = 15
SESSION_ID_PATTERN = re.compile(r"^(?:hml|prd)-\d{4}-\d{2}-\d{2}$")


class ActiveLifecycleRunError(RuntimeError):
    """Raised when teardown could still be mutating the environment."""


def _list_repository_runs(
    repository: str,
    ref: str,
    created_after: datetime,
    *,
    token: str,
    timeout_seconds: float = API_LOOKUP_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    if not cross_repo_lifecycle.REPOSITORY_PATTERN.fullmatch(repository):
        raise ActiveLifecycleRunError("A lifecycle repository is malformed; the audit cannot proceed.")
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", ref) or ".." in ref:
        raise ActiveLifecycleRunError("A lifecycle branch ref is malformed; the audit cannot proceed.")

    created_filter = ">=" + created_after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = urlencode(
        {
            "event": "workflow_dispatch",
            "branch": ref,
            "created": created_filter,
            "per_page": "100",
        }
    )
    result = cross_repo_lifecycle._api_request(
        token,
        "GET",
        f"/repos/{repository}/actions/runs?{query}",
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(result, dict) or not isinstance(result.get("workflow_runs"), list):
        raise ActiveLifecycleRunError("GitHub returned an invalid lifecycle run response; audit skipped.")
    if not isinstance(result.get("total_count"), int) or result["total_count"] > 100:
        raise ActiveLifecycleRunError("Too many lifecycle runs to verify safely; audit skipped.")
    runs = result["workflow_runs"]
    if not all(isinstance(run, dict) for run in runs):
        raise ActiveLifecycleRunError("GitHub returned malformed lifecycle run entries; audit skipped.")
    return runs


def _belongs_to_session(role: str, title: object, session_id: str) -> bool:
    if not isinstance(title, str):
        return False
    if role == "app":
        return title.startswith(f"lifecycle:{session_id}:app-deploy:")
    if role == "database":
        return title.startswith(f"database/{session_id}/")
    return title.startswith(f"{session_id}-")


def assert_no_active_session_runs(
    *,
    token: str,
    app_repository: str,
    app_ref: str,
    k8s_repository: str,
    k8s_ref: str,
    database_repository: str,
    database_ref: str,
    session_id: str,
    session_mode: str,
    started_at: str,
    wait_seconds: int = 0,
    poll_seconds: int = 15,
) -> None:
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        raise ActiveLifecycleRunError("The lifecycle session identifier is malformed; audit skipped.")
    if session_mode not in {"hml", "prd-window"}:
        raise ActiveLifecycleRunError("The lifecycle session mode is malformed; audit skipped.")
    if wait_seconds < 0 or poll_seconds <= 0:
        raise ActiveLifecycleRunError("The lifecycle audit wait settings are invalid; audit skipped.")
    if not token.strip():
        raise ActiveLifecycleRunError("The lifecycle API token is missing; audit skipped.")
    try:
        session_started_at = cross_repo_lifecycle._utc_timestamp(started_at)
    except cross_repo_lifecycle.LifecycleDispatchError as error:
        raise ActiveLifecycleRunError("The lifecycle session start time is malformed; audit skipped.") from error

    repositories = (
        ("app", app_repository, app_ref),
        ("k8s", k8s_repository, k8s_ref),
        ("database", database_repository, database_ref),
    )

    def active_run_error(active_runs: list[tuple[str, str]]) -> ActiveLifecycleRunError:
        details = "; ".join(f"active {role} lifecycle run ({run_id})" for role, run_id in active_runs[:5])
        return ActiveLifecycleRunError(
            f"{details} still match {session_id}; orphan audit skipped after waiting {wait_seconds} seconds."
        )

    deadline = time.monotonic() + wait_seconds
    last_active_runs: list[tuple[str, str]] = []
    while True:
        if wait_seconds > 0 and deadline - time.monotonic() <= 0:
            if last_active_runs:
                raise active_run_error(last_active_runs)
            raise ActiveLifecycleRunError(
                "GitHub could not be queried for every lifecycle repository before the audit deadline."
            )

        active_runs: list[tuple[str, str]] = []
        try:
            for role, repository, ref in repositories:
                remaining = deadline - time.monotonic()
                if wait_seconds > 0 and remaining <= 0:
                    if active_runs or last_active_runs:
                        raise active_run_error(active_runs or last_active_runs)
                    raise ActiveLifecycleRunError(
                        "The audit deadline expired before all lifecycle repositories could be checked."
                    )
                timeout_seconds = (
                    min(API_LOOKUP_TIMEOUT_SECONDS, remaining) if wait_seconds > 0 else API_LOOKUP_TIMEOUT_SECONDS
                )
                runs = _list_repository_runs(
                    repository,
                    ref,
                    session_started_at,
                    token=token,
                    timeout_seconds=timeout_seconds,
                )
                active_runs.extend(
                    (role, str(run.get("id", "unknown")))
                    for run in runs
                    if _belongs_to_session(role, run.get("display_title"), session_id)
                    and run.get("status") in cross_repo_lifecycle.ACTIVE_RUN_STATUSES
                )
        except cross_repo_lifecycle.LifecycleDispatchError as error:
            remaining = deadline - time.monotonic()
            if wait_seconds == 0 or remaining <= 0:
                if last_active_runs:
                    raise active_run_error(last_active_runs) from error
                raise ActiveLifecycleRunError(
                    "GitHub could not be queried for every lifecycle repository before the audit deadline."
                ) from error
            time.sleep(min(poll_seconds, remaining))
            continue

        if not active_runs:
            return

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise active_run_error(active_runs)
        last_active_runs = active_runs
        time.sleep(min(poll_seconds, remaining))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output")
    parser.add_argument("--wait-seconds", type=int, default=60)
    parser.add_argument("--poll-seconds", type=int, default=15)
    arguments = parser.parse_args()
    try:
        assert_no_active_session_runs(
            token=os.environ.get("LIFECYCLE_CROSS_REPO_TOKEN", ""),
            app_repository=os.environ.get("APP_REPOSITORY", ""),
            app_ref=os.environ.get("APP_REF", ""),
            k8s_repository=os.environ.get("K8S_INFRA_REPOSITORY", ""),
            k8s_ref=os.environ.get("K8S_INFRA_REF", ""),
            database_repository=os.environ.get("DATABASE_INFRA_REPOSITORY", ""),
            database_ref=os.environ.get("DATABASE_INFRA_REF", ""),
            session_id=os.environ.get("SESSION_ID", ""),
            session_mode=os.environ.get("SESSION_MODE", ""),
            started_at=os.environ.get("STARTED_AT", ""),
            wait_seconds=arguments.wait_seconds,
            poll_seconds=arguments.poll_seconds,
        )
    except (ActiveLifecycleRunError, cross_repo_lifecycle.LifecycleDispatchError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1

    print("No correlated app, K8s, or database lifecycle mutation is active; orphan audit may start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
