#!/usr/bin/env python3
"""Fail before lifecycle work starts after its absolute UTC deadline."""

import argparse
import sys
from datetime import datetime, timezone


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class LifecycleDeadlineError(ValueError):
    """Raised when teardown starts at or after its reserved-work deadline."""


def parse_deadline(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise LifecycleDeadlineError("The teardown deadline must use UTC format YYYY-MM-DDTHH:MM:SSZ.") from error
    if parsed.strftime(UTC_FORMAT) != value:
        raise LifecycleDeadlineError("The teardown deadline must use UTC format YYYY-MM-DDTHH:MM:SSZ.")
    return parsed


def assert_before_deadline(deadline: datetime, now: datetime) -> None:
    if deadline.tzinfo is None or deadline.utcoffset() != timezone.utc.utcoffset(deadline):
        raise LifecycleDeadlineError("The teardown deadline must be UTC-aware.")
    if now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(now):
        raise LifecycleDeadlineError("The current time must be UTC-aware.")
    if now >= deadline:
        raise LifecycleDeadlineError("The teardown work deadline has passed; only the reserved audit may run.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deadline-utc", required=True)
    arguments = parser.parse_args()
    try:
        deadline = parse_deadline(arguments.deadline_utc)
        assert_before_deadline(deadline, datetime.now(timezone.utc))
    except LifecycleDeadlineError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    print("The teardown work deadline is still open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
