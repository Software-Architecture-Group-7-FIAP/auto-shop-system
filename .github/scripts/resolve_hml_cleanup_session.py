#!/usr/bin/env python3
"""Find one expired HML session that still needs infrastructure cleanup."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from assert_lifecycle_close_needed import (
    FAILED_CONCLUSIONS,
    _opening_mutation_started,
    close_run_is_safe_to_retry,
)


API_ROOT = "https://api.github.com"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BRT = ZoneInfo("America/Sao_Paulo")
HML_LAST_DAY = date(2026, 11, 5)
MAX_RUNS = 1000
ACTIVE_STATUSES = {"queued", "requested", "waiting", "in_progress", "pending", "canceling"}
OPENING_APPLY_JOB_NAME = "apply reviewed saved plan"
OPENING_APPLY_STEP_NAME = "Verify and apply the exact saved plan"
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
OPENING_TITLE = re.compile(
    r"^lifecycle:hml:open:(default-17-BRT|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)(?::(?:[0-9a-f]{32}|\d+))?$"
)
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class HmlSession:
    session_id: str
    started_at: str
    run_id: int
    session_end: datetime
    cleanup_end: datetime


def _utc(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} has an invalid UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be a UTC timestamp")
    return parsed.astimezone(timezone.utc)


def _session_bounds(started_at: datetime) -> tuple[datetime, datetime]:
    local_start = started_at.astimezone(BRT)
    session_end = min(
        started_at + timedelta(hours=5),
        datetime.combine(local_start.date(), time(22, 0), tzinfo=BRT).astimezone(timezone.utc),
    )
    cleanup_end = min(
        session_end + timedelta(hours=1),
        datetime.combine(local_start.date(), time(23, 0), tzinfo=BRT).astimezone(timezone.utc),
    )
    return session_end, cleanup_end


def parse_hml_opening_run(
    run: dict[str, object], *, default_branch: str
) -> HmlSession | None:
    """Parse one default-branch manual HML opening run; ignore unrelated runs."""
    title = str(run.get("display_title", ""))
    if not title.startswith("lifecycle:hml:open:"):
        return None
    if run.get("head_branch") != default_branch or run.get("event") != "workflow_dispatch":
        return None
    match = OPENING_TITLE.fullmatch(title)
    if match is None:
        raise ValueError("malformed HML opening title")
    run_id = run.get("id")
    if not isinstance(run_id, int) or run_id < 1:
        raise ValueError("HML opening run has no valid numeric ID")

    created_at = _utc(run.get("created_at", ""), "HML opening creation time")
    start_label = match.group(1)
    if start_label == "default-17-BRT":
        local_day = created_at.astimezone(BRT).date()
        started_at = datetime.combine(local_day, time(17, 0), tzinfo=BRT).astimezone(timezone.utc)
    else:
        try:
            started_at = datetime.strptime(start_label, UTC_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError as error:
            raise ValueError("malformed HML opening title") from error
        if started_at.strftime(UTC_FORMAT) != start_label:
            raise ValueError("malformed HML opening title")

    local_start = started_at.astimezone(BRT)
    if local_start.date() > HML_LAST_DAY:
        raise ValueError("HML opening falls after the authorized HML lifecycle")
    if not time(7, 0) <= local_start.time().replace(tzinfo=None) <= time(17, 0):
        raise ValueError("HML opening start is outside the authorized daily window")
    if created_at < started_at:
        raise ValueError("HML opening run predates its declared session start")

    session_end, cleanup_end = _session_bounds(started_at)
    if created_at >= session_end:
        raise ValueError("HML opening run was created after its authorized session window")
    return HmlSession(
        session_id=f"hml-{local_start.date().isoformat()}",
        started_at=started_at.strftime(UTC_FORMAT),
        run_id=run_id,
        session_end=session_end,
        cleanup_end=cleanup_end,
    )


def find_cleanup_candidate(
    opening_runs: list[dict[str, object]],
    close_runs: list[dict[str, object]],
    *,
    default_branch: str,
    now: datetime,
    mutation_accepted,
    close_retry_safe,
) -> HmlSession | None:
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("HML cleanup time must be UTC-aware")

    sessions: dict[str, list[tuple[HmlSession, dict[str, object]]]] = {}
    for run in opening_runs:
        session = parse_hml_opening_run(run, default_branch=default_branch)
        if session is not None:
            sessions.setdefault(session.session_id, []).append((session, run))

    candidates: list[HmlSession] = []
    for session_id, openings in sessions.items():
        if len(openings) > 1:
            raise ValueError(f"multiple unclosed HML sessions have opening runs for {session_id}")
        session, opening_run = openings[0]
        if str(opening_run.get("status", "")) in ACTIVE_STATUSES:
            raise ValueError(f"HML opening run for {session_id} is still active; refusing concurrent teardown")
        if now < session.cleanup_end:
            continue

        close_prefix = f"lifecycle:hml:close:{session_id}:"
        prior_closes = [
            run for run in close_runs
            if str(run.get("display_title", "")).startswith(close_prefix)
        ]
        if any(
            run.get("status") == "completed" and run.get("conclusion") == "success"
            for run in prior_closes
        ):
            continue
        if any(str(run.get("status", "")) in ACTIVE_STATUSES for run in prior_closes):
            raise ValueError(f"an HML close run for {session_id} is still active; refusing cleanup")
        failed_closes = [
            run for run in prior_closes
            if run.get("status") == "completed" and run.get("conclusion") in FAILED_CONCLUSIONS
        ]
        unexpected = [run for run in prior_closes if run not in failed_closes]
        if unexpected:
            raise ValueError(f"an HML close run for {session_id} has an unknown state")
        if any(not close_retry_safe(run) for run in failed_closes):
            raise ValueError(
                f"an HML close run for {session_id} may have entered teardown; operator phase review is required"
            )
        if mutation_accepted(session, opening_run):
            candidates.append(session)

    if len(candidates) > 1:
        raise ValueError("multiple unclosed HML sessions require cleanup; refusing to guess")
    return candidates[0] if candidates else None


def _api_request(token: str, path: str) -> object:
    request = Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "auto-shop-hml-cleanup-coordinator",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _workflow_runs(
    repository: str,
    workflow: str,
    token: str,
    *,
    branch: str = "",
    created_after: datetime | None = None,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    page = 1
    total_count: int | None = None
    while True:
        query_values = {"event": "workflow_dispatch", "per_page": "100", "page": str(page)}
        if branch:
            query_values["branch"] = branch
        if created_after is not None:
            query_values["created"] = ">=" + created_after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = _api_request(
            token,
            f"/repos/{repository}/actions/workflows/{workflow}/runs?{urlencode(query_values)}",
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
            raise ValueError(f"GitHub returned an invalid {workflow} run listing")
        count = payload.get("total_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"GitHub returned an invalid {workflow} run count")
        if total_count is None:
            total_count = count
            if total_count > MAX_RUNS:
                raise ValueError(f"More than {MAX_RUNS} {workflow} runs prevent a safe cleanup decision")
        elif count != total_count:
            raise ValueError(f"GitHub changed the {workflow} run count during pagination")
        entries = payload["workflow_runs"]
        if not all(isinstance(run, dict) for run in entries):
            raise ValueError(f"GitHub returned malformed {workflow} run entries")
        result.extend(entries)
        if len(result) >= total_count:
            break
        if not entries:
            raise ValueError(f"GitHub returned an incomplete {workflow} run listing")
        page += 1
    if total_count is None or len(result) != total_count:
        raise ValueError(f"GitHub returned an incomplete {workflow} run listing")
    run_ids = [run.get("id") for run in result]
    if any(isinstance(run_id, bool) or not isinstance(run_id, int) or run_id < 1 for run_id in run_ids):
        raise ValueError(f"GitHub returned invalid {workflow} run IDs")
    if len(set(run_ids)) != len(run_ids):
        raise ValueError(f"GitHub returned duplicate {workflow} run IDs")
    return result


def _workflow_jobs(repository: str, run_id: int, token: str) -> list[dict[str, object]]:
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id < 1:
        raise ValueError("The correlated upstream apply has no valid numeric run ID")
    result: list[dict[str, object]] = []
    page = 1
    total_count: int | None = None
    while True:
        query_values = {"filter": "all", "per_page": "100", "page": str(page)}
        payload = _api_request(
            token,
            f"/repos/{repository}/actions/runs/{run_id}/jobs?{urlencode(query_values)}",
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("GitHub returned an invalid upstream apply job listing")
        count = payload.get("total_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("GitHub returned an invalid upstream apply job count")
        if total_count is None:
            total_count = count
            if total_count > MAX_RUNS:
                raise ValueError("Too many upstream apply attempts prevent a safe cleanup decision")
        elif count != total_count:
            raise ValueError("GitHub changed the upstream apply job count during pagination")
        entries = payload["jobs"]
        if not all(isinstance(job, dict) for job in entries):
            raise ValueError("GitHub returned malformed upstream apply job entries")
        result.extend(entries)
        if len(result) >= total_count:
            break
        if not entries:
            raise ValueError("GitHub returned an incomplete upstream apply job listing")
        page += 1
    if total_count is None or len(result) != total_count:
        raise ValueError("GitHub returned an incomplete upstream apply job listing")
    job_ids = [job.get("id") for job in result]
    if any(isinstance(job_id, bool) or not isinstance(job_id, int) or job_id < 1 for job_id in job_ids):
        raise ValueError("GitHub returned invalid upstream apply job IDs")
    if len(set(job_ids)) != len(job_ids):
        raise ValueError("GitHub returned duplicate upstream apply job IDs")
    return result


def _opening_apply_step_started(jobs: list[dict[str, object]]) -> bool:
    matching_jobs = [job for job in jobs if job.get("name") == OPENING_APPLY_JOB_NAME]
    if not matching_jobs:
        raise ValueError("The expected opening apply job is missing from upstream run evidence")

    for job in matching_jobs:
        if job.get("status") in ACTIVE_STATUSES:
            raise ValueError("The correlated upstream opening apply job is still active")
        if job.get("status") == "completed" and job.get("conclusion") == "skipped":
            continue
        steps = job.get("steps")
        if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
            raise ValueError("The upstream opening apply step evidence is missing or ambiguous")
        apply_steps = [step for step in steps if step.get("name") == OPENING_APPLY_STEP_NAME]
        if len(apply_steps) != 1 or "started_at" not in apply_steps[0]:
            raise ValueError("The upstream opening apply step evidence is missing or ambiguous")
        started_at = apply_steps[0]["started_at"]
        if started_at is not None and not isinstance(started_at, str):
            raise ValueError("The upstream opening apply step evidence is invalid")
        if started_at:
            return True
    return False


def has_accepted_opening_apply_run(
    runs: list[dict[str, object]],
    *,
    session_id: str,
    ref: str,
    started_after: datetime,
    jobs_for_run: Callable[[int], list[dict[str, object]]],
) -> bool:
    """Require the exact correlated upstream run and its scoped apply step to have started."""
    if started_after.tzinfo is None or started_after.utcoffset() != timedelta(0):
        raise ValueError("Opening creation time must be UTC-aware")
    expected_title = re.compile(rf"^{re.escape(session_id)}-foundation-open-apply:[0-9a-f]{{32}}$")
    matches = []
    for run in runs:
        if run.get("event") != "workflow_dispatch" or run.get("head_branch") != ref:
            continue
        if not expected_title.fullmatch(str(run.get("display_title", ""))):
            continue
        created_at = _utc(run.get("created_at", ""), "upstream opening apply creation time")
        if created_at >= started_after.astimezone(timezone.utc):
            matches.append(run)

    if any(str(run.get("status", "")) in ACTIVE_STATUSES for run in matches):
        raise ValueError("The correlated upstream opening apply is still active; refusing emergency cleanup")
    if len(matches) > 1:
        raise ValueError("Multiple correlated upstream opening applies are ambiguous; refusing emergency cleanup")
    for run in matches:
        if (
            run.get("status") != "completed"
            or run.get("conclusion") not in COMPLETED_CONCLUSIONS
        ):
            raise ValueError("The correlated upstream opening apply has an unknown state")
        run_id = run.get("id")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id < 1:
            raise ValueError("The correlated upstream opening apply has no valid numeric run ID")
        jobs = jobs_for_run(run_id)
        if not isinstance(jobs, list) or not all(isinstance(job, dict) for job in jobs):
            raise ValueError("GitHub returned malformed upstream opening apply job evidence")
        if _opening_apply_step_started(jobs):
            return True
    return False


def _opening_apply_was_accepted(
    session: HmlSession,
    opening_run: dict[str, object],
    *,
    coordinator_repository: str,
    infrastructure_repository: str,
    ref: str,
    token: str,
) -> bool:
    run_id = session.run_id
    if not _opening_mutation_started(coordinator_repository, run_id, token):
        return False
    opened_at = _utc(opening_run.get("created_at", ""), "HML opening creation time")
    upstream_runs = _workflow_runs(
        infrastructure_repository,
        "apply.yml",
        token,
        branch=ref,
        created_after=opened_at,
    )
    return has_accepted_opening_apply_run(
        upstream_runs,
        session_id=session.session_id,
        ref=ref,
        started_after=opened_at,
        jobs_for_run=lambda run_id: _workflow_jobs(infrastructure_repository, run_id, token),
    )


def _write_output(path: str, name: str, value: str) -> None:
    if "\n" in value or "\r" in value:
        raise ValueError("GitHub output cannot contain line breaks")
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", required=True)
    arguments = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    ref_name = os.environ.get("GITHUB_REF_NAME", "").strip()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "").strip()
    token = os.environ.get("LIFECYCLE_CROSS_REPO_TOKEN", "").strip()
    infrastructure_repository = os.environ.get("K8S_INFRA_REPOSITORY", "").strip()
    infrastructure_ref = os.environ.get("K8S_INFRA_REF", "").strip()
    if not repository or not token or event_name not in {"schedule", "workflow_dispatch"}:
        print("::error::HML cleanup requires a supported event, repository, and explicit lifecycle token.", file=sys.stderr)
        return 1
    if not REPOSITORY_PATTERN.fullmatch(infrastructure_repository) or infrastructure_ref != "main":
        print("::error::HML cleanup requires the configured K8S infrastructure repository and main ref.", file=sys.stderr)
        return 1

    try:
        repository_info = _api_request(token, f"/repos/{repository}")
        if not isinstance(repository_info, dict) or not isinstance(repository_info.get("default_branch"), str):
            raise ValueError("GitHub returned an invalid repository default branch")
        default_branch = repository_info["default_branch"]
        if ref_name != default_branch:
            raise ValueError("HML cleanup may run only from the repository's default branch")

        opening_runs = _workflow_runs(
            repository, "environment-start.yml", token, branch=default_branch
        )
        close_runs = _workflow_runs(repository, "environment-stop.yml", token)
        candidate = find_cleanup_candidate(
            opening_runs,
            close_runs,
            default_branch=default_branch,
            now=datetime.now(timezone.utc),
            mutation_accepted=lambda session, opening_run: _opening_apply_was_accepted(
                session,
                opening_run,
                coordinator_repository=repository,
                infrastructure_repository=infrastructure_repository,
                ref=infrastructure_ref,
                token=token,
            ),
            close_retry_safe=lambda run: close_run_is_safe_to_retry(repository, run, token),
        )
        if candidate is None:
            reason = "No expired HML session with an unclosed infrastructure mutation was found."
            _write_output(arguments.github_output, "close_needed", "false")
            _write_output(arguments.github_output, "decision", reason)
            print(reason)
            return 0

        _write_output(arguments.github_output, "close_needed", "true")
        _write_output(arguments.github_output, "session_id", candidate.session_id)
        _write_output(arguments.github_output, "started_at", candidate.started_at)
        _write_output(arguments.github_output, "opening_run_id", str(candidate.run_id))
        _write_output(arguments.github_output, "decision", "One expired HML session needs emergency cleanup.")
        print(f"Resolved one expired HML cleanup candidate: {candidate.session_id}.")
    except (HTTPError, URLError, OSError, json.JSONDecodeError, ValueError) as error:
        print(f"::error::HML cleanup discovery failed closed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
