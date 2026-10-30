#!/usr/bin/env python3
"""Fail closed unless this BRT session has an opening that still needs closing."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, time, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


API_ROOT = "https://api.github.com"
BRT = ZoneInfo("America/Sao_Paulo")
SESSION_PATTERN = re.compile(r"^(?:hml|prd)-(\d{4}-\d{2}-\d{2})$")
ACTIVE_STATUSES = {"queued", "requested", "waiting", "in_progress", "pending"}
FIRST_MUTATION_MARKER = "Apply the exact K8s foundation opening plan"
RUN_TITLE_SUFFIX = re.compile(r"(?::[0-9a-f]{32}|:\d+)$")


def _matches_opening_title(title: str, base_title: str) -> bool:
    if title == base_title:
        return True
    suffix = title[len(base_title):] if title.startswith(f"{base_title}:") else ""
    return bool(suffix and RUN_TITLE_SUFFIX.fullmatch(suffix))


def _runs(repository: str, workflow: str, local_day: date, token: str) -> list[dict[str, object]]:
    day_start = datetime.combine(local_day, time.min, tzinfo=BRT).astimezone(timezone.utc)
    query = urlencode({
        "created": ">=" + day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_page": "100",
    })
    request = Request(
        f"{API_ROOT}/repos/{repository}/actions/workflows/{workflow}/runs?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "auto-shop-lifecycle-coordinator",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        raise ValueError("GitHub returned an invalid workflow run listing")
    if int(payload.get("total_count", 0)) > 100:
        raise ValueError(f"More than 100 {workflow} runs prevent a safe idempotency check")
    return [run for run in payload["workflow_runs"] if isinstance(run, dict)]


def _runs_for_brt_day(runs: list[dict[str, object]], local_day: date) -> list[dict[str, object]]:
    result = []
    for run in runs:
        try:
            created = datetime.fromisoformat(str(run.get("created_at", "")).replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("A candidate lifecycle run has an invalid creation timestamp") from error
        if created.astimezone(BRT).date() == local_day:
            result.append(run)
    return result


def _opening_mutation_started(repository: str, run_id: object, token: str) -> bool:
    request = Request(
        f"{API_ROOT}/repos/{repository}/actions/runs/{run_id}/jobs?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "auto-shop-lifecycle-coordinator",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("GitHub returned an invalid opening job listing")
    total_count = payload.get("total_count")
    if not isinstance(total_count, int):
        raise ValueError("GitHub returned an invalid job count")
    if total_count > 100:
        raise ValueError("Too many jobs prevent a safe opening-mutation check")
    open_jobs = [job for job in payload["jobs"] if isinstance(job, dict) and job.get("name") == "open"]
    if len(open_jobs) > 1:
        raise ValueError("Multiple coordinator open jobs were found; refusing teardown")
    if not open_jobs:
        return False
    if open_jobs[0].get("conclusion") == "skipped":
        return False
    steps = open_jobs[0].get("steps")
    if not isinstance(steps, list):
        raise ValueError("The coordinator open job has no readable step list")
    markers = [
        step for step in steps
        if isinstance(step, dict) and step.get("name") == FIRST_MUTATION_MARKER
    ]
    if len(markers) != 1:
        raise ValueError("The expected first-mutation marker is missing or ambiguous; refusing teardown")
    return bool(markers[0].get("started_at"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--close-request-id", default="")
    parser.add_argument("--github-output", required=True)
    arguments = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    current_run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    token = os.environ.get("LIFECYCLE_CROSS_REPO_TOKEN", "").strip()
    if not repository or not current_run_id or not token:
        print("::error::Close idempotency requires repository, run ID, and the explicit cross-repository token.", file=sys.stderr)
        return 1
    if arguments.close_request_id and not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", arguments.close_request_id):
        print("::error::close_request_id may contain only letters, digits, dot, underscore, and hyphen (maximum 64 characters).", file=sys.stderr)
        return 1

    match = SESSION_PATTERN.fullmatch(arguments.session_id)
    if not match or not arguments.session_id.startswith(f"{arguments.stage}-"):
        print("::error::The resolved session ID is not valid for the requested lifecycle stage.", file=sys.stderr)
        return 1
    try:
        session_day = date.fromisoformat(match.group(1))
        started_at = datetime.strptime(arguments.started_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        print("::error::The resolved session date or started_at value is invalid.", file=sys.stderr)
        return 1
    if started_at.astimezone(BRT).date() != session_day:
        print("::error::The resolved session start does not belong to the session's BRT date.", file=sys.stderr)
        return 1
    if datetime.now(timezone.utc).astimezone(BRT).date() != session_day:
        print("::error::The close guard is outside the session's BRT calendar day.", file=sys.stderr)
        return 1

    try:
        opening_runs = _runs_for_brt_day(
            _runs(repository, "environment-start.yml", session_day, token), session_day
        )
        title_prefix = f"lifecycle:{arguments.stage}:open:"
        matching_openings = [
            run for run in opening_runs
            if str(run.get("display_title", "")).startswith(title_prefix)
        ]
        if arguments.stage == "hml":
            expected_opening_title = f"{title_prefix}{arguments.started_at}"
            default_opening_title = f"{title_prefix}default-17-BRT"
            is_default_session = started_at.astimezone(BRT).strftime("%H:%M:%S") == "17:00:00"
            matching_openings = [
                run for run in matching_openings
                if _matches_opening_title(str(run.get("display_title", "")), expected_opening_title)
                or (
                    is_default_session
                    and _matches_opening_title(str(run.get("display_title", "")), default_opening_title)
                )
            ]
        if len(matching_openings) > 1:
            raise ValueError("Multiple matching opening runs were found; refusing teardown")
        if not matching_openings:
            close_needed = False
            reason = "No matching opening run exists for this session; no infrastructure was changed."
        else:
            opening = matching_openings[0]
            if arguments.stage == "prd" and str(opening.get("status", "")) in ACTIVE_STATUSES:
                raise ValueError("The PRD opening run is still active; refusing teardown before it finishes")
            if not isinstance(opening.get("id"), int):
                raise ValueError("The matching opening run has no valid numeric ID")
            if not _opening_mutation_started(repository, opening.get("id"), token):
                close_needed = False
                reason = "The matching opening run never started a mutating lifecycle step; no teardown was run."
                with open(arguments.github_output, "a", encoding="utf-8") as output_file:
                    output_file.write("close_needed=false\n")
                    output_file.write(f"decision={reason}\n")
                print(reason)
                return 0
            close_runs = _runs_for_brt_day(
                _runs(repository, "environment-stop.yml", session_day, token), session_day
            )
            close_prefix = f"lifecycle:{arguments.stage}:close:{arguments.session_id}"
            if arguments.stage == "prd":
                close_prefix = f"lifecycle:{arguments.stage}:close:"
            prior_closes = [
                run for run in close_runs
                if str(run.get("id")) != current_run_id
                and str(run.get("display_title", "")).startswith(close_prefix)
            ]
            if any(str(run.get("conclusion", "")) == "success" for run in prior_closes):
                close_needed = False
                reason = "A successful close already exists for this session; no duplicate teardown was started."
            elif any(str(run.get("status", "")) in ACTIVE_STATUSES for run in prior_closes):
                raise ValueError("Another close run is still active; refusing a concurrent teardown")
            else:
                close_needed = True
                reason = "A matching opening exists and no successful close has completed."
    except (HTTPError, URLError, OSError, json.JSONDecodeError, ValueError) as error:
        print(f"::error::Close idempotency check failed closed: {error}", file=sys.stderr)
        return 1

    with open(arguments.github_output, "a", encoding="utf-8") as output_file:
        output_file.write(f"close_needed={str(close_needed).lower()}\n")
        output_file.write(f"decision={reason}\n")
    print(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
