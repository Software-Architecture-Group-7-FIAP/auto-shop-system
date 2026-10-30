#!/usr/bin/env python3
"""Wait for the independent audit window without crossing its cleanup deadline."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone


WAIT_INTERVAL_SECONDS = 30


class AuditDeadlineError(ValueError):
    """Raised when the requested audit window cannot be reached safely."""


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AuditDeadlineError("Audit times must be ISO-8601 UTC timestamps.") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise AuditDeadlineError("Audit times must be ISO-8601 UTC timestamps.")
    return parsed.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def wait_until_utc(target_utc: str, deadline_utc: str) -> None:
    target = _parse_utc(target_utc)
    deadline = _parse_utc(deadline_utc)
    if target >= deadline:
        raise AuditDeadlineError("The audit start must be before the cleanup deadline.")

    while True:
        now = _utc_now()
        if now >= deadline:
            raise AuditDeadlineError("The cleanup deadline passed before the audit window opened.")
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(WAIT_INTERVAL_SECONDS, remaining))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-utc", required=True)
    parser.add_argument("--deadline-utc", required=True)
    arguments = parser.parse_args()
    try:
        wait_until_utc(arguments.target_utc, arguments.deadline_utc)
    except AuditDeadlineError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    print("The independent orphan audit window is open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
