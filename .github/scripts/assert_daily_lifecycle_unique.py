#!/usr/bin/env python3
"""Reject a second HML or PRD opening run on the same BRT calendar day."""

from __future__ import annotations

import os
import json
import argparse
import sys
from datetime import date, datetime, time, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


BRT = ZoneInfo("America/Sao_Paulo")
API_ROOT = "https://api.github.com"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    arguments = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    current_run_id = os.environ.get("GITHUB_RUN_ID", "")
    token = os.environ.get("LIFECYCLE_CROSS_REPO_TOKEN", "").strip()
    if not repository or not current_run_id or not token:
        print("::error::Unique-session check requires repository, run ID, and the explicit cross-repository token.", file=sys.stderr)
        return 1

    local_day = datetime.now(timezone.utc).astimezone(BRT).date()
    day_start_utc = datetime.combine(local_day, time(0, 0), tzinfo=BRT).astimezone(timezone.utc)
    query = urlencode({
        "created": ">=" + day_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_page": "100",
    })
    request = Request(
        f"{API_ROOT}/repos/{repository}/actions/workflows/environment-start.yml/runs?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "auto-shop-prd-lifecycle-coordinator",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
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

    # Only block if there's a successful prior run on the same day.
    # Failed attempts can be retried on the same day.
    successful_prior_runs = [
        run for run in matching_runs
        if str(run.get("id")) != current_run_id and run.get("conclusion") == "success"
    ]
    if successful_prior_runs:
        print(f"::error::A successful {arguments.stage.upper()} opening run already exists for today; only retrying failed runs is allowed.", file=sys.stderr)
        return 1
    if len(matching_runs) > 1:
        # Multiple runs on same day are allowed if none are successful (all are failures/in-progress)
        failed_count = sum(1 for run in matching_runs if str(run.get("id")) != current_run_id)
        if failed_count > 0:
            print(f"Previous {arguments.stage.upper()} opening run(s) failed today; retrying is allowed.")
        else:
            print("::error::Multiple HML starts were found for today; refusing to continue.", file=sys.stderr)
            return 1

    print(f"No earlier {arguments.stage.upper()} lifecycle opening was found for {local_day.isoformat()} BRT.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
