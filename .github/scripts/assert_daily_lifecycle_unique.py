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
SESSION_RECORD_STEP_NAME = "Record the trusted operator and authorize an infrastructure-only session"
FOUNDATION_PLAN_STEP_NAME = "Plan the K8s foundation opening"
INFRASTRUCTURE_APPLY_STEP_NAMES = (
    "Apply the exact K8s foundation opening plan",
    "Apply the exact K8s platform opening plan",
    "Apply the exact HML namespace opening plan",
    "Bootstrap the HML lifecycle database",
)


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


def _attempt_jobs(run_id: int, attempt: int, repository: str, token: str) -> list[dict[str, object]]:
    jobs_url = f"{API_ROOT}/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100"
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
    return jobs


def _is_safe_before_session(opening_job: dict[str, object]) -> bool:
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


def _safe_session_recovery_attempt(opening_job: dict[str, object]) -> tuple[bool, bool]:
    """Return whether a failed attempt is safe for handoff and whether it recorded state."""
    if opening_job.get("status") != "completed" or opening_job.get("conclusion") != "failure":
        return False, False
    steps = opening_job.get("steps")
    if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
        return False, False

    record_steps = [step for step in steps if step.get("name") == SESSION_RECORD_STEP_NAME]
    plan_steps = [step for step in steps if step.get("name") == FOUNDATION_PLAN_STEP_NAME]
    if len(record_steps) != 1 or len(plan_steps) != 1:
        return False, False
    apply_steps: list[dict[str, object]] = []
    for name in INFRASTRUCTURE_APPLY_STEP_NAMES:
        matches = [step for step in steps if step.get("name") == name]
        if len(matches) != 1:
            return False, False
        apply_steps.append(matches[0])

    record_step = record_steps[0]
    plan_step = plan_steps[0]
    record_conclusion = record_step.get("conclusion")
    plan_conclusion = plan_step.get("conclusion")
    recorded = record_step.get("status") == "completed" and record_conclusion == "success"
    record_failed = record_step.get("status") == "completed" and record_conclusion == "failure"
    plan_failed = plan_step.get("status") == "completed" and plan_conclusion == "failure"
    plan_skipped = plan_step.get("status") == "completed" and plan_conclusion == "skipped"
    all_applies_skipped = all(
        step.get("status") == "completed" and step.get("conclusion") == "skipped"
        for step in apply_steps
    )

    failed_at_record_then_plan_skipped = record_failed and plan_skipped
    failed_at_plan_after_record = recorded and plan_failed
    return (all_applies_skipped and (failed_at_record_then_plan_skipped or failed_at_plan_after_record), recorded)


def _inspect_retryable_run(run: dict[str, object], repository: str, token: str) -> tuple[bool, str | None]:
    conclusion = run.get("conclusion")
    if (
        run.get("status") != "completed"
        or not isinstance(conclusion, str)
        or conclusion not in RETRYABLE_RUN_CONCLUSIONS
    ):
        return False, None
    try:
        run_id = int(run.get("id", 0))
        attempt_count = run.get("run_attempt")
    except (TypeError, ValueError):
        return False, None
    if (
        run_id <= 0
        or not isinstance(attempt_count, int)
        or isinstance(attempt_count, bool)
        or attempt_count < 1
        or attempt_count > 100
    ):
        return False, None

    saw_recovery_attempt = False
    saw_successful_session_record = False
    for attempt in range(1, attempt_count + 1):
        jobs = _attempt_jobs(run_id, attempt, repository, token)
        opening_jobs = [job for job in jobs if job.get("name") == OPENING_JOB_NAME]
        if len(opening_jobs) != 1:
            return False, None
        opening_job = opening_jobs[0]
        if _is_safe_before_session(opening_job):
            continue

        recovery_safe, recorded = _safe_session_recovery_attempt(opening_job)
        if not recovery_safe:
            return False, None
        saw_recovery_attempt = True
        saw_successful_session_record = saw_successful_session_record or recorded

    if saw_recovery_attempt:
        if conclusion != "failure":
            return False, None
        # A failed ledger-record step may have left no state, or its response may have
        # been lost. Do not use that run as the owner: a later coordinator attempt must
        # either hand off the older verified owner or fail closed against the ledger.
        return True, str(run_id) if saw_successful_session_record else None
    return True, None


def _write_recovery_output(source_run_id: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not output_path:
        if source_run_id:
            raise ValueError("GitHub Actions output is required to publish the verified recovery source.")
        return
    if "\n" in source_run_id or "\r" in source_run_id:
        raise ValueError("The recovery source run ID is malformed.")
    with open(output_path, "a", encoding="utf-8") as output_file:
        output_file.write(f"recovery_source_run_id={source_run_id}\n")


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
    total_runs = result.get("total_count")
    if not isinstance(total_runs, int) or isinstance(total_runs, bool):
        print("::error::GitHub returned an invalid workflow-run count.", file=sys.stderr)
        return 1
    if total_runs > 100:
        print("::error::Too many workflow runs to verify today's HML session safely.", file=sys.stderr)
        return 1
    if any(not isinstance(run, dict) for run in result["workflow_runs"]):
        print("::error::GitHub returned an invalid workflow run.", file=sys.stderr)
        return 1

    matching_runs = []
    matching_run_created_at: dict[str, datetime] = {}
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
            matching_run_created_at[str(run.get("id"))] = created_at

    prior_runs = [run for run in matching_runs if str(run.get("id")) != current_run_id]
    recovery_source_run_ids: list[str] = []
    try:
        for run in prior_runs:
            safe, recovery_source_run_id = _inspect_retryable_run(run, repository, token)
            if not safe:
                print(
                    f"::error::An earlier {arguments.stage.upper()} opening is active or may have started "
                    "AWS changes; refusing to retry.",
                    file=sys.stderr,
                )
                return 1
            if recovery_source_run_id:
                recovery_source_run_ids.append(recovery_source_run_id)
    except (HTTPError, URLError, OSError, json.JSONDecodeError, ValueError):
        print(
            "::error::Could not verify whether a previous opening started AWS changes; refusing to continue.",
            file=sys.stderr,
        )
        return 1

    recovery_source_run_id = ""
    if recovery_source_run_ids:
        recovery_source_run_id = max(
            recovery_source_run_ids,
            key=lambda source_id: (matching_run_created_at[source_id], int(source_id)),
        )

    try:
        _write_recovery_output(recovery_source_run_id)
    except (OSError, ValueError):
        print("::error::Could not publish the verified lifecycle recovery source.", file=sys.stderr)
        return 1

    if prior_runs:
        print(
            f"Found {len(prior_runs)} completed {arguments.stage.upper()} attempt(s) that stopped before "
            "AWS infrastructure applies; allowing this guarded retry."
        )
        if recovery_source_run_id:
            print(f"Verified safe ledger ownership recovery from most recent failed run {recovery_source_run_id}.")
    else:
        print(f"No earlier {arguments.stage.upper()} lifecycle opening was found for {local_day.isoformat()} BRT.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
