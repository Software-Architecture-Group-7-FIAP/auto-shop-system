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
FAILED_CONCLUSIONS = {"failure", "cancelled", "timed_out", "startup_failure", "action_required"}
COMPLETED_CONCLUSIONS = {
    "success",
    "failure",
    "cancelled",
    "timed_out",
    "startup_failure",
    "action_required",
    "neutral",
    "skipped",
    "stale",
}
FIRST_MUTATION_MARKER = "Apply the exact K8s foundation opening plan"
CLOSE_MUTATION_MARKERS = (
    "Apply the reviewed HML namespace teardown plan",
    "Destroy the ephemeral HML database",
    "Apply the reviewed K8s platform teardown plan",
    "Apply the reviewed compute-only foundation teardown plan",
    "Apply the reviewed NAT shutdown plan",
)
RUN_TITLE_SUFFIX = re.compile(r"(?::[0-9a-f]{32}|:\d+)$")


def _matches_opening_title(title: str, base_title: str) -> bool:
    if title == base_title:
        return True
    suffix = title[len(base_title):] if title.startswith(f"{base_title}:") else ""
    return bool(suffix and RUN_TITLE_SUFFIX.fullmatch(suffix))


def _runs(repository: str, workflow: str, local_day: date, token: str) -> list[dict[str, object]]:
    day_start = datetime.combine(local_day, time.min, tzinfo=BRT).astimezone(timezone.utc)
    results: list[dict[str, object]] = []
    expected_count: int | None = None
    page = 1
    while expected_count is None or len(results) < expected_count:
        query = urlencode({
            "created": ">=" + day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "per_page": "100",
            "page": str(page),
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
            raise ValueError(f"GitHub returned an invalid {workflow} run listing")
        total_count = payload.get("total_count")
        entries = payload["workflow_runs"]
        if isinstance(total_count, bool) or not isinstance(total_count, int) or total_count < 0:
            raise ValueError(f"GitHub returned an invalid {workflow} run count")
        if total_count > 100:
            raise ValueError(f"More than 100 {workflow} runs prevent a safe idempotency check")
        if expected_count is None:
            expected_count = total_count
        elif total_count != expected_count:
            raise ValueError(f"GitHub returned an inconsistent {workflow} run count")
        if not all(isinstance(run, dict) for run in entries):
            raise ValueError(f"GitHub returned malformed {workflow} run entries")
        results.extend(entries)
        run_ids = [run.get("id") for run in results]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError(f"GitHub returned duplicate {workflow} run IDs")
        if len(results) >= expected_count:
            break
        if not entries:
            raise ValueError(f"GitHub returned an incomplete {workflow} run listing")
        page += 1
    if expected_count is None or len(results) != expected_count:
        raise ValueError(f"GitHub returned an incomplete {workflow} run listing")
    return results


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
        f"{API_ROOT}/repos/{repository}/actions/runs/{run_id}/jobs?filter=all&per_page=100",
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
    if total_count > 100 or total_count != len(payload["jobs"]):
        raise ValueError("The opening job listing is incomplete; refusing teardown")
    if not all(isinstance(job, dict) for job in payload["jobs"]):
        raise ValueError("The opening job listing contains malformed entries")
    return has_started_mutating_job(payload["jobs"])


def has_started_mutating_job(jobs: list[dict[str, object]]) -> bool:
    """Find mutation across every opening attempt so a rerun cannot hide earlier work."""
    open_jobs = [job for job in jobs if job.get("name") == "open"]
    for open_job in open_jobs:
        if open_job.get("conclusion") == "skipped":
            continue
        steps = open_job.get("steps")
        if not isinstance(steps, list):
            raise ValueError("The coordinator open job has no readable step list")
        markers = [step for step in steps if isinstance(step, dict) and step.get("name") == FIRST_MUTATION_MARKER]
        if len(markers) != 1:
            raise ValueError("The expected first-mutation marker is missing or ambiguous; refusing teardown")
        marker = markers[0]
        if marker.get("conclusion") == "skipped":
            continue
        if marker.get("started_at") or marker.get("conclusion") is not None:
            return True
        raise ValueError("The first-mutation marker has no conclusive execution state; refusing teardown")
    return False


def close_run_proves_no_mutation(jobs: list[dict[str, object]]) -> bool:
    """Require complete evidence that every possible teardown mutation was skipped."""
    close_jobs = [job for job in jobs if job.get("name") == "close"]
    if len(close_jobs) != 1:
        return False
    steps = close_jobs[0].get("steps")
    if not isinstance(steps, list):
        return False
    for marker_name in CLOSE_MUTATION_MARKERS:
        markers = [step for step in steps if isinstance(step, dict) and step.get("name") == marker_name]
        if len(markers) != 1:
            return False
        marker = markers[0]
        if marker.get("conclusion") == "skipped":
            continue
        if marker.get("started_at") or marker.get("conclusion") is not None:
            return False
    return True


def close_run_is_safe_to_retry(repository: str, run: dict[str, object], token: str) -> bool:
    """Check if a failed close run is safe to retry (failed before teardown started)."""
    run_id = run.get("id")
    if not isinstance(run_id, int):
        raise ValueError("Close run has no valid numeric ID")
    attempts = run.get("run_attempt", 1)
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise ValueError("Close run has an invalid attempt count")
    if str(run.get("status", "")) in ACTIVE_STATUSES:
        return False
    try:
        for attempt in range(1, attempts + 1):
            request = Request(
                f"{API_ROOT}/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100",
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
                raise ValueError("GitHub returned an invalid close job listing")
            jobs = payload["jobs"]
            total_count = payload.get("total_count")
            if not isinstance(total_count, int) or total_count != len(jobs) or total_count > 100:
                raise ValueError("GitHub returned an incomplete close job listing")
            if not all(isinstance(job, dict) for job in jobs):
                raise ValueError("GitHub returned malformed close jobs")
            if not close_run_proves_no_mutation(jobs):
                return False
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Failed to fetch close run jobs: {error}") from error
    return True


def emergency_cleanup_is_authorized(
    *,
    stage: str,
    close_request_id: str,
    event_name: str,
    workflow: str,
    ref: str,
    capability_verified: str,
) -> bool:
    return (
        stage == "hml"
        and re.fullmatch(r"emergency-[1-9][0-9]{0,19}", close_request_id) is not None
        and event_name == "workflow_dispatch"
        and workflow == "HML infrastructure-only stop"
        and ref == "refs/heads/develop"
        and capability_verified == "true"
    )


def _opening_close_decision(
    matching_openings: list[dict[str, object]], repository: str, token: str
) -> tuple[bool, bool, str]:
    if not matching_openings:
        return False, False, "No matching opening run exists for this session; no infrastructure was changed."

    mutating_openings: list[dict[str, object]] = []
    for opening in matching_openings:
        if str(opening.get("status", "")) in ACTIVE_STATUSES:
            raise ValueError("A matching opening run is still active; refusing teardown")
        run_id = opening.get("id")
        if not isinstance(run_id, int):
            raise ValueError("A matching opening run has no valid numeric ID")
        if _opening_mutation_started(repository, run_id, token):
            mutating_openings.append(opening)

    if len(mutating_openings) > 1:
        raise ValueError("Multiple mutating opening runs were found; refusing teardown")
    if not mutating_openings:
        reason = (
            "Matching opening runs completed without starting a mutating lifecycle step; "
            "close the ledger after the read-only audit without teardown."
        )
        return True, False, reason
    return True, True, "A matching opening run started a mutating lifecycle step; guarded teardown is required."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--close-request-id", default="")
    parser.add_argument("--cleanup-dispatch", action="store_true")
    parser.add_argument("--emergency-cleanup", action="store_true")
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
    if arguments.cleanup_dispatch and arguments.emergency_cleanup:
        print("::error::Choose only one cleanup authorization mode.", file=sys.stderr)
        return 1
    if arguments.emergency_cleanup and not emergency_cleanup_is_authorized(
        stage=arguments.stage,
        close_request_id=arguments.close_request_id,
        event_name=os.environ.get("GITHUB_EVENT_NAME", ""),
        workflow=os.environ.get("GITHUB_WORKFLOW", ""),
        ref=os.environ.get("GITHUB_REF", ""),
        capability_verified=os.environ.get("LIFECYCLE_EMERGENCY_CAPABILITY_VERIFIED", ""),
    ):
        print("::error::Emergency cleanup requires a verified HML capability on the develop stop workflow.", file=sys.stderr)
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
    if (
        not arguments.cleanup_dispatch
        and not arguments.emergency_cleanup
        and datetime.now(timezone.utc).astimezone(BRT).date() != session_day
    ):
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
        close_needed, teardown_needed, reason = _opening_close_decision(
            matching_openings, repository, token
        )
        if close_needed:
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
                teardown_needed = False
                reason = "A successful close already exists for this session; no duplicate teardown was started."
            elif any(str(run.get("status", "")) in ACTIVE_STATUSES for run in prior_closes):
                raise ValueError("Another close run is still active; refusing a concurrent teardown")
    except (HTTPError, URLError, OSError, json.JSONDecodeError, ValueError) as error:
        print(f"::error::Close idempotency check failed closed: {error}", file=sys.stderr)
        return 1

    with open(arguments.github_output, "a", encoding="utf-8") as output_file:
        output_file.write(f"close_needed={str(close_needed).lower()}\n")
        output_file.write(f"teardown_needed={str(teardown_needed).lower()}\n")
        output_file.write(f"decision={reason}\n")
    print(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
