#!/usr/bin/env python3
"""Reject a second HML or PRD opening run on the same BRT calendar day."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, time, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


BRT = ZoneInfo("America/Sao_Paulo")
API_ROOT = "https://api.github.com"
OPENING_JOB_NAME = "open"
RETRYABLE_RUN_CONCLUSIONS = {"failure", "cancelled", "timed_out"}
UNIQUE_GUARD_STEP_NAME = "Reject a second opening run for the same HML date"
FIRST_MUTATION_STEP_NAME = "Configure the narrow lifecycle start role"


def _github_get_json(url: str, token: str) -> object:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "auto-shop-lifecycle-coordinator",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _is_safe_retryable_attempt(run: dict[str, object], repository: str, token: str) -> bool:
    conclusion = run.get("conclusion")
    if (
        run.get("status") != "completed"
        or not isinstance(conclusion, str)
        or conclusion not in RETRYABLE_RUN_CONCLUSIONS
    ):
        return False
    try:
        run_id = int(run.get("id", 0))
    except (TypeError, ValueError):
        return False
    if run_id <= 0:
        return False

    jobs_url = f"{API_ROOT}/repos/{repository}/actions/runs/{run_id}/jobs?per_page=100"
    jobs_result = _github_get_json(jobs_url, token)
    if not isinstance(jobs_result, dict) or not isinstance(jobs_result.get("jobs"), list):
        raise ValueError("GitHub returned an invalid workflow-job listing.")
    total_jobs = jobs_result.get("total_count")
    if (
        not isinstance(total_jobs, int)
        or isinstance(total_jobs, bool)
        or total_jobs > 100
        or total_jobs != len(jobs_result["jobs"])
    ):
        raise ValueError("GitHub returned an incomplete workflow-job listing.")

    jobs = jobs_result["jobs"]
    if any(not isinstance(job, dict) for job in jobs):
        raise ValueError("GitHub returned an invalid workflow job.")
    opening_jobs = [job for job in jobs if job.get("name") == OPENING_JOB_NAME]
    if len(opening_jobs) != 1:
        return False
    opening_job = opening_jobs[0]
    if opening_job.get("status") != "completed":
        return False
    if opening_job.get("conclusion") == "skipped":
        return True
    if opening_job.get("conclusion") != "failure":
        return False

    steps = opening_job.get("steps")
    if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
        return False
    guard_steps = [step for step in steps if step.get("name") == UNIQUE_GUARD_STEP_NAME]
    mutation_steps = [step for step in steps if step.get("name") == FIRST_MUTATION_STEP_NAME]
    if len(guard_steps) != 1 or len(mutation_steps) != 1:
        return False
    guard_step = guard_steps[0]
    mutation_step = mutation_steps[0]
    return (
        steps.index(guard_step) < steps.index(mutation_step)
        and guard_step.get("status") == "completed"
        and guard_step.get("conclusion") == "failure"
        and mutation_step.get("status") == "completed"
        and mutation_step.get("conclusion") == "skipped"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    arguments = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    current_run_id = os.environ.get("GITHUB_RUN_ID", "")
    token = os.environ.get("LIFECYCLE_CROSS_REPO_TOKEN", "").strip()
    if not repository or not current_run_id or not token:
        print(
            "::error::Unique-session check requires repository, run ID, and the explicit cross-repository token.",
            file=sys.stderr,
        )
        return 1

    local_day = datetime.now(timezone.utc).astimezone(BRT).date()
    day_start_utc = datetime.combine(local_day, time(0, 0), tzinfo=BRT).astimezone(timezone.utc)
    query = urlencode({
        "created": ">=" + day_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_page": "100",
    })
    try:
        result = _github_get_json(
            f"{API_ROOT}/repos/{repository}/actions/workflows/environment-start.yml/runs?{query}",
            token,
        )
    except (HTTPError, URLError, OSError, json.JSONDecodeError):
        print("::error::Could not verify whether an HML session was already started today.", file=sys.stderr)
        return 1

    if not isinstance(result, dict) or not isinstance(result.get("workflow_runs"), list):
        print("::error::GitHub returned an invalid workflow-run listing.", file=sys.stderr)
        return 1
    if int(result.get("total_count", 0)) > 100:
        print("::error::Too many workflow runs to verify today's HML session safely.", file=sys.stderr)
        return 1

    matching_runs = []
    for run in result["workflow_runs"]:
        title = str(run.get("display_title", ""))
        if not title.startswith(f"lifecycle:{arguments.stage}:open:"):
            continue
        try:
            created_at = datetime.fromisoformat(str(run.get("created_at", "")).replace("Z", "+00:00"))
        except ValueError:
            print("::error::A candidate HML workflow has an invalid creation timestamp.", file=sys.stderr)
            return 1
        if created_at.astimezone(BRT).date() == local_day:
            matching_runs.append(run)

    prior_runs = [run for run in matching_runs if str(run.get("id")) != current_run_id]
    try:
        if any(not _is_safe_retryable_attempt(run, repository, token) for run in prior_runs):
            print(
                f"::error::An earlier {arguments.stage.upper()} opening is active or may have started "
                "AWS changes; refusing to retry.",
                file=sys.stderr,
            )
            return 1
    except (HTTPError, URLError, OSError, json.JSONDecodeError, ValueError):
        print(
            "::error::Could not verify whether a previous opening started AWS changes; refusing to continue.",
            file=sys.stderr,
        )
        return 1

    if prior_runs:
        print(
            f"Found {len(prior_runs)} completed {arguments.stage.upper()} attempt(s) that stopped before "
            "AWS mutations; allowing this guarded retry."
        )
    else:
        print(f"No earlier {arguments.stage.upper()} lifecycle opening was found for {local_day.isoformat()} BRT.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
