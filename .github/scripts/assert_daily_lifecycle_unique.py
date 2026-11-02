#!/usr/bin/env python3
"""Reject a second HML or PRD opening run on the same BRT calendar day."""

from __future__ import annotations

import os
import json
import argparse
import re
import sys
from datetime import date, datetime, time, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


BRT = ZoneInfo("America/Sao_Paulo")
API_ROOT = "https://api.github.com"
ACTIVE_STATUSES = {"queued", "requested", "waiting", "in_progress", "pending"}
GUARD_STEP_NAME = "Reject a second opening run for the same HML date"
FIRST_MUTATION_STEP_NAME = "Configure the narrow lifecycle start role"
SESSION_RECORD_STEP_NAME = "Record the trusted operator and authorize the selected HML session profile"
FOUNDATION_PLAN_STEP_NAME = "Plan the K8s foundation opening"
INFRASTRUCTURE_APPLY_STEP_NAMES = (
    "Apply the exact K8s foundation opening plan",
    "Apply the exact K8s platform opening plan",
    "Apply the exact HML namespace opening plan",
    "Bootstrap the synthetic lifecycle database",
)


def _api_json(path: str, token: str) -> dict[str, object]:
    request = Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "auto-shop-lifecycle-coordinator",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned an invalid lifecycle response")
    return payload


def _workflow_runs(repository: str, local_day: date, token: str) -> list[dict[str, object]]:
    day_start_utc = datetime.combine(local_day, time.min, tzinfo=BRT).astimezone(timezone.utc)
    query = urlencode({
        "created": ">=" + day_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_page": "100",
    })
    payload = _api_json(
        f"/repos/{repository}/actions/workflows/environment-start.yml/runs?{query}", token
    )
    runs = payload.get("workflow_runs")
    total_count = payload.get("total_count")
    if not isinstance(runs, list) or not isinstance(total_count, int) or total_count < len(runs):
        raise ValueError("GitHub returned an invalid workflow-run listing")
    if total_count > 100 or total_count != len(runs):
        raise ValueError("The workflow-run listing is incomplete; refusing a duplicate-session decision")
    if not all(isinstance(run, dict) for run in runs):
        raise ValueError("GitHub returned a malformed workflow-run entry")
    return runs


def _attempt_jobs(repository: str, run_id: int, attempt: int, token: str) -> list[dict[str, object]]:
    payload = _api_json(
        f"/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100", token
    )
    jobs = payload.get("jobs")
    total_count = payload.get("total_count")
    if not isinstance(jobs, list) or not isinstance(total_count, int) or total_count != len(jobs):
        raise ValueError("GitHub returned an incomplete opening-job listing")
    if total_count > 100 or not all(isinstance(job, dict) for job in jobs):
        raise ValueError("GitHub returned an invalid opening-job listing")
    return jobs


def _step_conclusion(steps: list[object], name: str) -> str | None:
    matches = [step for step in steps if isinstance(step, dict) and step.get("name") == name]
    if len(matches) != 1:
        return None
    conclusion = matches[0].get("conclusion")
    return conclusion if isinstance(conclusion, str) else None


def _classify_prior_run(
    repository: str,
    run: dict[str, object],
    token: str,
    *,
    last_attempt: int | None = None,
) -> tuple[bool, bool]:
    """Return (safe_to_retry, verified_ledger_owner), failing closed on ambiguity."""
    run_id = run.get("id")
    run_attempt = run.get("run_attempt")
    if not isinstance(run_id, int) or not isinstance(run_attempt, int) or run_attempt < 1:
        raise ValueError("A prior opening run has no valid ID or attempt count")
    if last_attempt is None:
        last_attempt = run_attempt
    if last_attempt < 1 or last_attempt > run_attempt:
        raise ValueError("A prior opening run has an invalid attempt boundary")

    verified_owner = False
    safe_to_retry = True
    for attempt in range(1, last_attempt + 1):
        jobs = _attempt_jobs(repository, run_id, attempt, token)
        open_jobs = [job for job in jobs if job.get("name") == "open"]
        if len(open_jobs) != 1:
            raise ValueError("A prior opening attempt has missing or ambiguous open-job evidence")
        open_job = open_jobs[0]
        if open_job.get("conclusion") == "skipped":
            continue
        steps = open_job.get("steps")
        if not isinstance(steps, list):
            raise ValueError("A prior opening attempt has no readable step evidence")

        record_state = _step_conclusion(steps, SESSION_RECORD_STEP_NAME)
        plan_state = _step_conclusion(steps, FOUNDATION_PLAN_STEP_NAME)
        guard_state = _step_conclusion(steps, GUARD_STEP_NAME)
        mutation_state = _step_conclusion(steps, FIRST_MUTATION_STEP_NAME)
        if guard_state == "failure" and mutation_state == "skipped":
            continue

        apply_states = [_step_conclusion(steps, name) for name in INFRASTRUCTURE_APPLY_STEP_NAMES]
        if any(state is None for state in apply_states):
            raise ValueError("A prior opening attempt is missing infrastructure apply evidence")
        if any(state != "skipped" for state in apply_states):
            safe_to_retry = False

        # A recorded session whose foundation plan failed is an authorized handoff,
        # provided every mutating apply step stayed skipped in every attempt.
        if record_state == "success" and plan_state == "failure":
            verified_owner = True
            continue
        if record_state in {"failure", "skipped"} and plan_state == "skipped":
            continue
        raise ValueError("A prior opening attempt has ambiguous pre-mutation evidence")

    return safe_to_retry, verified_owner and safe_to_retry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    arguments = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    current_run_id = os.environ.get("GITHUB_RUN_ID", "")
    raw_current_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip()
    token = os.environ.get("LIFECYCLE_CROSS_REPO_TOKEN", "").strip()
    if not repository or not current_run_id or not token or not re.fullmatch(r"[1-9][0-9]*", raw_current_attempt):
        print("::error::Unique-session check requires repository, run ID, and the explicit cross-repository token.", file=sys.stderr)
        return 1
    current_attempt = int(raw_current_attempt)

    local_day = datetime.now(timezone.utc).astimezone(BRT).date()
    try:
        runs = _workflow_runs(repository, local_day, token)
        matching_runs = []
        for run in runs:
            title = str(run.get("display_title", ""))
            if not title.startswith(f"lifecycle:{arguments.stage}:open:"):
                continue
            created_at = datetime.fromisoformat(str(run.get("created_at", "")).replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                raise ValueError("A candidate lifecycle run has a timezone-free creation timestamp")
            if created_at.astimezone(BRT).date() == local_day:
                matching_runs.append(run)

        current_run = next(
            (run for run in matching_runs if str(run.get("id")) == current_run_id), None
        )
        if current_attempt > 1:
            if current_run is None:
                raise ValueError("The current rerun is missing from today's opening-run evidence")
            run_attempt = current_run.get("run_attempt")
            if not isinstance(run_attempt, int) or run_attempt < current_attempt:
                raise ValueError("The current rerun has incomplete attempt evidence")
            safe, verified = _classify_prior_run(
                repository,
                current_run,
                token,
                last_attempt=current_attempt - 1,
            )
            if not safe:
                raise ValueError("An earlier attempt of this workflow run may have started infrastructure mutation")
            if verified:
                raise ValueError(
                    "An earlier attempt already owns the lifecycle ledger; dispatch a new workflow run for recovery"
                )

        prior_runs = [run for run in matching_runs if str(run.get("id")) != current_run_id]
        if any(str(run.get("status", "")) in ACTIVE_STATUSES for run in prior_runs):
            raise ValueError("A prior opening run is still active; refusing a second opening")
        if any(run.get("conclusion") == "success" for run in prior_runs):
            raise ValueError(f"A successful {arguments.stage.upper()} opening run already exists today.")

        verified_owners: list[tuple[datetime, int]] = []
        for run in prior_runs:
            safe, verified = _classify_prior_run(repository, run, token)
            if not safe:
                raise ValueError("A prior opening attempt may have started infrastructure mutation")
            if verified:
                created_at = datetime.fromisoformat(str(run["created_at"]).replace("Z", "+00:00"))
                verified_owners.append((created_at, int(run["id"])))

        if verified_owners:
            source_run_id = max(verified_owners, key=lambda item: item[0])[1]
            output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
            if not output_path:
                raise ValueError("A verified recovery handoff requires GITHUB_OUTPUT")
            with open(output_path, "a", encoding="utf-8") as output_file:
                output_file.write(f"recovery_source_run_id={source_run_id}\n")
            print(f"Verified safe recovery handoff from lifecycle run {source_run_id}.")
            return 0
    except (HTTPError, URLError, OSError, json.JSONDecodeError, ValueError) as error:
        print(f"::error::Could not verify today's lifecycle opening safely: {error}", file=sys.stderr)
        return 1

    print(f"No earlier {arguments.stage.upper()} lifecycle opening blocks {local_day.isoformat()} BRT.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
