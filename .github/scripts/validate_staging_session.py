import argparse
import os
import sys
from datetime import datetime, timedelta, timezone


MAX_SESSION_DURATION = timedelta(hours=5)
STARTED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class StagingSessionError(ValueError):
    """Raised when a staging session is missing, unauthorized, or expired."""


def _parse_started_at(value: str) -> datetime:
    if not value:
        raise StagingSessionError("STAGING_SESSION_STARTED_AT is required.")

    try:
        parsed = datetime.strptime(value, STARTED_AT_FORMAT)
    except ValueError as error:
        raise StagingSessionError(
            "STAGING_SESSION_STARTED_AT must use UTC format YYYY-MM-DDTHH:MM:SSZ."
        ) from error

    if parsed.strftime(STARTED_AT_FORMAT) != value:
        raise StagingSessionError(
            "STAGING_SESSION_STARTED_AT must use UTC format YYYY-MM-DDTHH:MM:SSZ."
        )

    return parsed.replace(tzinfo=timezone.utc)


def validate_staging_session(
    *,
    active: str,
    authorized: str,
    session_id: str,
    started_at: str,
    now: datetime,
    minimum_remaining_seconds: int = 0,
) -> timedelta:
    if active != "true":
        raise StagingSessionError("STAGING_ACTIVE must be true.")
    if authorized != "true":
        raise StagingSessionError("STAGING_SESSION_AUTHORIZED must be true.")
    if not session_id.strip():
        raise StagingSessionError("STAGING_SESSION_ID is required.")
    if (
        isinstance(minimum_remaining_seconds, bool)
        or not isinstance(minimum_remaining_seconds, int)
        or minimum_remaining_seconds < 0
    ):
        raise StagingSessionError("The minimum remaining time must be a non-negative integer.")
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise StagingSessionError("The current time must be UTC-aware.")

    start = _parse_started_at(started_at)
    elapsed = now - start
    if elapsed < timedelta(0):
        raise StagingSessionError("STAGING_SESSION_STARTED_AT is in the future.")

    remaining = MAX_SESSION_DURATION - elapsed
    if remaining <= timedelta(0):
        raise StagingSessionError("The staging session reached its five-hour limit.")
    if remaining < timedelta(seconds=minimum_remaining_seconds):
        raise StagingSessionError("There is not enough remaining session time for this job.")

    return remaining


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an authorized staging session.")
    parser.add_argument("--minimum-remaining-seconds", type=int, default=0)
    arguments = parser.parse_args()

    try:
        remaining = validate_staging_session(
            active=os.environ.get("STAGING_ACTIVE", ""),
            authorized=os.environ.get("STAGING_SESSION_AUTHORIZED", ""),
            session_id=os.environ.get("STAGING_SESSION_ID", ""),
            started_at=os.environ.get("STAGING_SESSION_STARTED_AT", ""),
            now=datetime.now(timezone.utc),
            minimum_remaining_seconds=arguments.minimum_remaining_seconds,
        )
    except StagingSessionError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1

    print(f"Staging session is valid; {int(remaining.total_seconds())} seconds remain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
