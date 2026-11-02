#!/usr/bin/env python3
"""Dispatch the coordinated stop workflow for each expired ledger session."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from lifecycle_session_auth import LifecycleSessionAuthError, sign_lifecycle_session


SESSION_PATTERN = re.compile(r"^(hml|prd)-(\d{4}-\d{2}-\d{2})$")
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _load_sessions(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("The expired lifecycle session list is missing or malformed.") from error
    if not isinstance(value, list):
        raise ValueError("The expired lifecycle session list must be a JSON array.")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError("The expired lifecycle session list contains a malformed record.")
    return value


def _validate_session(item: dict[str, Any]) -> tuple[str, str, str, str] | None:
    session_id = item.get("session_id")
    stage = item.get("stage")
    started_at = item.get("started_at")
    session_mode = item.get("session_mode")
    if not all(isinstance(value, str) for value in (session_id, stage, started_at, session_mode)):
        raise ValueError("An expired ledger item is missing required session fields.")
    match = SESSION_PATTERN.fullmatch(session_id)
    if match is None or match.group(1) != stage:
        raise ValueError("An expired ledger item has an invalid stage or session ID.")
    if stage != "hml" or item.get("session_scope") != "infrastructure-only":
        return None
    try:
        parsed_started_at = datetime.strptime(started_at, UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError("An expired ledger item has an invalid started_at value.") from error
    if parsed_started_at.strftime(UTC_FORMAT) != started_at or parsed_started_at.date().isoformat() != match.group(2):
        raise ValueError("An expired ledger item has a start time outside its session date.")
    expected_mode = "hml"
    if session_mode != expected_mode or item.get("status") not in {"active", "closing"}:
        raise ValueError("An expired ledger item has an invalid mode or state.")
    return session_id, stage, started_at, session_mode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", required=True)
    parser.add_argument("--deadline-utc", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--limit", type=int, default=4)
    arguments = parser.parse_args()

    try:
        deadline = datetime.strptime(arguments.deadline_utc, UTC_FORMAT).replace(tzinfo=timezone.utc)
        if deadline.strftime(UTC_FORMAT) != arguments.deadline_utc:
            raise ValueError("The cleanup deadline is not canonical UTC.")
        sessions = _load_sessions(Path(arguments.sessions))
        if len(sessions) > 100:
            raise ValueError("The expired lifecycle session query exceeded its hard safety limit.")
        if arguments.limit < 1 or arguments.limit > 4:
            raise ValueError("The cleanup dispatch limit must be between one and four sessions.")
        results = []
        failures = 0
        excluded = 0
        for item in sessions:
            session = _validate_session(item)
            if session is None:
                excluded += 1
                continue
            if len(results) >= arguments.limit:
                break
            session_id, stage, started_at, session_mode = session
            close_request_id = f"cleanup-{session_id}"
            inputs = {
                "stage": stage,
                "session_id": session_id,
                "started_at": started_at,
                "session_mode": session_mode,
                "session_scope": "infrastructure-only",
                "close_request_id": close_request_id,
            }
            session_token = sign_lifecycle_session(
                os.environ.get("LIFECYCLE_SESSION_SIGNING_KEY", ""),
                session_mode,
                session_id,
                started_at,
                allow_hml_any_time=os.environ.get("STAGING_SESSION_ALLOW_ANY_TIME", "").lower() == "true",
            )
            index = len(results) + 1
            command = [
                sys.executable,
                ".github/scripts/cross_repo_lifecycle.py",
                "--repository",
                "${GITHUB_REPOSITORY}",
                "--workflow",
                "environment-stop.yml",
                "--ref",
                "main",
                "--expected-title",
                f"lifecycle:{stage}:close:{session_id}:{close_request_id}",
                "--inputs",
                json.dumps(inputs, sort_keys=True, separators=(",", ":")),
                "--authorization-action",
                "cleanup-close",
                "--github-output",
                str(Path(arguments.results).with_suffix(f".{index}.out")),
                "--output-name",
                "cleanup",
                "--timeout-seconds",
                "3600",
                "--deadline-utc",
                arguments.deadline_utc,
            ]
            command[command.index("${GITHUB_REPOSITORY}")] = os.environ.get("GITHUB_REPOSITORY", "")
            if not command[command.index("--repository") + 1]:
                raise ValueError("GITHUB_REPOSITORY is required for cleanup dispatch.")
            child_environment = os.environ.copy()
            child_environment.pop("LIFECYCLE_SESSION_SIGNING_KEY", None)
            child_environment["LIFECYCLE_SESSION_TOKEN"] = session_token
            completed = subprocess.run(command, check=False, env=child_environment)
            status = "success" if completed.returncode == 0 else "failure"
            failures += completed.returncode != 0
            results.append({"session_id": session_id, "stage": stage, "status": status})
        Path(arguments.results).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(
            f"Attempted teardown for {len(results)} expired infrastructure-only HML session(s); "
            f"excluded={excluded}; failures={failures}."
        )
        return 1 if failures else 0
    except (LifecycleSessionAuthError, OSError, ValueError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
