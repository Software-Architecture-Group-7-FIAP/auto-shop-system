#!/usr/bin/env python3
"""Cancel and wait for deployments belonging to one lifecycle session."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
ACTIVE_STATUSES = {"queued", "waiting", "pending", "requested", "in_progress", "canceling"}


class LifecycleCancelError(RuntimeError):
    """Raised when a deployment cannot be safely stopped and observed."""


def _request(token: str, method: str, path: str, *, timeout_seconds: float = 30) -> Any:
    request = Request(
        f"{API_ROOT}{path}",
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "auto-shop-lifecycle-coordinator",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status in {202, 204}:
                return None
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise LifecycleCancelError(f"GitHub API request failed with HTTP {error.code}.") from error
    except (URLError, json.JSONDecodeError) as error:
        raise LifecycleCancelError("GitHub API could not be reached or returned invalid JSON.") from error


def _active_runs(
    token: str,
    repository: str,
    workflow: str,
    branch: str,
    title: str,
    *,
    timeout_seconds: float = 30,
) -> list[dict[str, Any]]:
    owner, repo_name = repository.split("/", 1)
    created_after = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = urlencode(
        {
            "branch": branch,
            "event": "workflow_dispatch",
            "created": ">=" + created_after,
            "per_page": "100",
        }
    )
    result = _request(
        token,
        "GET",
        f"/repos/{owner}/{repo_name}/actions/workflows/{workflow}/runs?{query}",
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(result, dict) or not isinstance(result.get("workflow_runs"), list):
        raise LifecycleCancelError("GitHub returned an invalid workflow-run listing.")
    if int(result.get("total_count", 0)) > 100:
        raise LifecycleCancelError("Too many recent runs to inspect safely before teardown.")

    matches: dict[int, dict[str, Any]] = {}
    for run in result["workflow_runs"]:
        run_id = run.get("id")
        run_title = run.get("display_title")
        if (
            isinstance(run_title, str)
            and (run_title == title or run_title.startswith(f"{title}:"))
            and run.get("status") in ACTIVE_STATUSES
            and isinstance(run_id, int)
        ):
            matches[run_id] = run
    return list(matches.values())


def cancel_and_wait(arguments: argparse.Namespace) -> int:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("LIFECYCLE_CROSS_REPO_TOKEN", "").strip()
    if "/" not in repository or not token:
        raise LifecycleCancelError(
            "Cancel-and-wait requires GITHUB_REPOSITORY and the explicit LIFECYCLE_CROSS_REPO_TOKEN."
        )
    branch = "develop" if arguments.stage == "hml" else "main"
    workflow = "cd-staging.yml" if arguments.stage == "hml" else "cd-prod.yml"
    expected_title = f"lifecycle:{arguments.session_id}:app-deploy"
    remaining_seconds = float(arguments.timeout_seconds)
    if arguments.deadline_utc:
        try:
            deadline_utc = datetime.strptime(arguments.deadline_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError as error:
            raise LifecycleCancelError("The lifecycle deadline must use UTC format YYYY-MM-DDTHH:MM:SSZ.") from error
        if deadline_utc.strftime("%Y-%m-%dT%H:%M:%SZ") != arguments.deadline_utc:
            raise LifecycleCancelError("The lifecycle deadline must use UTC format YYYY-MM-DDTHH:MM:SSZ.")
        remaining_seconds = min(remaining_seconds, (deadline_utc - datetime.now(timezone.utc)).total_seconds())
    if remaining_seconds <= 0:
        raise LifecycleCancelError("The lifecycle teardown deadline has already passed.")
    deadline = time.monotonic() + remaining_seconds

    remaining = deadline - time.monotonic()
    active_runs = _active_runs(
        token,
        repository,
        workflow,
        branch,
        expected_title,
        timeout_seconds=min(30, remaining),
    )
    for run in active_runs:
        run_id = run["id"]
        if run.get("status") in ACTIVE_STATUSES:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LifecycleCancelError("The lifecycle teardown deadline expired before deployment cancellation.")
            owner, repo_name = repository.split("/", 1)
            _request(
                token,
                "POST",
                f"/repos/{owner}/{repo_name}/actions/runs/{run_id}/cancel",
                timeout_seconds=min(30, remaining),
            )
            print(f"Requested cancellation of active {workflow} run {run_id}.")

    while time.monotonic() < deadline:
        request_budget = deadline - time.monotonic()
        if request_budget <= 0:
            break
        remaining_runs = _active_runs(
            token,
            repository,
            workflow,
            branch,
            expected_title,
            timeout_seconds=min(30, request_budget),
        )
        if not remaining_runs:
            print(f"No active {workflow} deployments remain for {arguments.session_id}.")
            return 0
        time.sleep(min(arguments.poll_seconds, max(0, deadline - time.monotonic())))

    raise LifecycleCancelError(
        f"A {workflow} deployment remained active past the teardown wait limit."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--deadline-utc", default="")
    arguments = parser.parse_args()
    if arguments.timeout_seconds < 1 or arguments.poll_seconds < 1:
        print("::error::Timeout and polling intervals must be positive.", file=sys.stderr)
        return 1
    try:
        return cancel_and_wait(arguments)
    except (LifecycleCancelError, OSError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
