#!/usr/bin/env python3
"""Find one expired HML session that still needs infrastructure cleanup."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from assert_lifecycle_close_needed import _opening_mutation_started


API_ROOT = "https://api.github.com"
BRT = ZoneInfo("America/Sao_Paulo")
HML_LAST_DAY = date(2026, 10, 31)
MAX_RUNS = 1000
ACTIVE_STATUSES = {"queued", "requested", "waiting", "in_progress", "pending", "canceling"}
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
    mutation_started,
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
            continue
        unexpected = [
            run for run in prior_closes
            if run.get("status") != "completed"
            or run.get("conclusion") not in {"failure", "cancelled", "timed_out", "startup_failure"}
        ]
        if unexpected:
            raise ValueError(f"an HML close run for {session_id} has an unknown state")
        if mutation_started(session.run_id):
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
    repository: str, workflow: str, token: str, *, branch: str = ""
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    page = 1
    total_count: int | None = None
    while True:
        query_values = {"event": "workflow_dispatch", "per_page": "100", "page": str(page)}
        if branch:
            query_values["branch"] = branch
        payload = _api_request(
            token,
            f"/repos/{repository}/actions/workflows/{workflow}/runs?{urlencode(query_values)}",
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
            raise ValueError(f"GitHub returned an invalid {workflow} run listing")
        count = payload.get("total_count")
        if not isinstance(count, int):
            raise ValueError(f"GitHub returned an invalid {workflow} run count")
        if total_count is None:
            total_count = count
            if total_count > MAX_RUNS:
                raise ValueError(f"More than {MAX_RUNS} {workflow} runs prevent a safe cleanup decision")
        entries = payload["workflow_runs"]
        if not all(isinstance(run, dict) for run in entries):
            raise ValueError(f"GitHub returned malformed {workflow} run entries")
        result.extend(entries)
        if len(result) >= total_count or not entries:
            break
        page += 1
    return result


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
    if not repository or not token or event_name not in {"schedule", "workflow_dispatch"}:
        print("::error::HML cleanup requires a supported event, repository, and explicit lifecycle token.", file=sys.stderr)
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
            mutation_started=lambda run_id: _opening_mutation_started(repository, run_id, token),
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
