import argparse
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from lifecycle_session_auth import (
    LifecycleSessionAuthError,
    verify_emergency_hml_cleanup,
    verify_lifecycle_session,
)


BRT = ZoneInfo("America/Sao_Paulo")
MAX_HML_DURATION = timedelta(hours=5)
HML_LAST_DAY = date(2026, 10, 31)
PRD_FIRST_DAY = date(2026, 11, 1)
PRD_LAST_DAY = date(2026, 11, 5)
STARTED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SUPPORTED_ACTIONS = frozenset({"start", "health", "operate", "teardown"})
SUPPORTED_STAGES = frozenset({"hml", "prd"})


class EnvironmentWindowError(ValueError):
    """Raised when an environment action is outside its authorized window."""


def _parse_started_at(value: str) -> datetime:
    if not value:
        raise EnvironmentWindowError("ENVIRONMENT_WINDOW_STARTED_AT is required.")

    try:
        parsed = datetime.strptime(value, STARTED_AT_FORMAT)
    except ValueError as error:
        raise EnvironmentWindowError(
            "ENVIRONMENT_WINDOW_STARTED_AT must use UTC format YYYY-MM-DDTHH:MM:SSZ."
        ) from error

    if parsed.strftime(STARTED_AT_FORMAT) != value:
        raise EnvironmentWindowError(
            "ENVIRONMENT_WINDOW_STARTED_AT must use UTC format YYYY-MM-DDTHH:MM:SSZ."
        )

    return parsed.replace(tzinfo=timezone.utc)


def _require_session_gate(
    *, active: str, authorized: str, session_id: str, action: str
) -> None:
    # Cleanup must remain possible even when an operator disabled or revoked a session.
    if action == "teardown":
        return
    if active != "true":
        raise EnvironmentWindowError("ENVIRONMENT_ACTIVE must be true.")
    if authorized != "true":
        raise EnvironmentWindowError("The environment window must be explicitly authorized.")
    if not session_id.strip():
        raise EnvironmentWindowError("ENVIRONMENT_SESSION_ID is required.")


def _inside(local_time: time, *, start: time, end: time) -> bool:
    return start <= local_time < end


def _validate_prd_window(
    *, action: str, now: datetime, started_at: datetime, emergency_teardown: bool
) -> None:
    local_now = now.astimezone(BRT)
    local_day = local_now.date()

    if not PRD_FIRST_DAY <= local_day <= PRD_LAST_DAY:
        raise EnvironmentWindowError(
            "PRD is authorized only from 01/11/2026 through 05/11/2026 in BRT."
        )

    if started_at.astimezone(BRT).date() != local_day:
        raise EnvironmentWindowError("PRD requires a window start from the current BRT day.")
    if started_at.astimezone(BRT).time().replace(tzinfo=None) != time(6, 0):
        raise EnvironmentWindowError("PRD requires the coordinator's fixed 06:00 BRT session start.")

    if action == "teardown" and emergency_teardown:
        return

    allowed_times = {
        "start": (time(6, 0), time(7, 0), "06:00-07:00"),
        "health": (time(6, 45), time(22, 0), "06:45-22:00"),
        "operate": (time(7, 0), time(22, 0), "07:00-22:00"),
        "teardown": (time(22, 0), time(23, 0), "22:00-23:00"),
    }
    start, end, label = allowed_times[action]
    if not _inside(local_now.time(), start=start, end=end):
        raise EnvironmentWindowError(
            f"PRD action '{action}' is allowed only from {label} BRT."
        )


def validate_environment_window(
    *,
    active: str,
    authorized: str,
    session_id: str,
    stage: str,
    action: str,
    started_at: str,
    now: datetime,
    emergency_teardown: bool = False,
    emergency_hml_teardown: bool = False,
) -> timedelta | None:
    if stage not in SUPPORTED_STAGES:
        raise EnvironmentWindowError("ENVIRONMENT_STAGE must be hml or prd.")
    if action not in SUPPORTED_ACTIONS:
        raise EnvironmentWindowError(
            "The action must be start, health, operate, or teardown."
        )
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise EnvironmentWindowError("The current time must be UTC-aware.")
    if emergency_teardown and stage != "prd":
        raise EnvironmentWindowError("The existing emergency teardown flag is available only for PRD.")
    if emergency_hml_teardown and (stage != "hml" or action != "teardown"):
        raise EnvironmentWindowError("Emergency cleanup is available only for HML teardown.")

    _require_session_gate(
        active=active,
        authorized=authorized,
        session_id=session_id,
        action=action,
    )
    start = _parse_started_at(started_at)
    expected_session_id = f"{stage}-{start.astimezone(BRT).date().isoformat()}"
    if session_id != expected_session_id:
        raise EnvironmentWindowError(
            f"ENVIRONMENT_SESSION_ID must match the coordinator's {stage} BRT session date."
        )
    elapsed = now - start
    if elapsed < timedelta(0):
        raise EnvironmentWindowError("ENVIRONMENT_WINDOW_STARTED_AT is in the future.")

    if stage == "hml":
        local_now = now.astimezone(BRT)
        hml_cutoff = datetime.combine(HML_LAST_DAY, time(23, 0), tzinfo=BRT)
        local_start = start.astimezone(BRT)
        if not emergency_hml_teardown and local_now >= hml_cutoff:
            raise EnvironmentWindowError(
                "HML lifecycle actions are authorized only before 23:00 BRT on 31/10/2026."
            )
        if local_start.date() > HML_LAST_DAY:
            raise EnvironmentWindowError("Emergency cleanup cannot target a session after the HML lifecycle.")
        if not emergency_hml_teardown and local_start.date() != local_now.date():
            raise EnvironmentWindowError("An HML session must start on the current BRT day.")
        start_time = local_start.time().replace(tzinfo=None)
        if not time(7, 0) <= start_time <= time(17, 0):
            raise EnvironmentWindowError(
                "HML sessions must start between 07:00 and 17:00 BRT."
            )
        day_end = datetime.combine(
            local_start.date(), time(22, 0), tzinfo=BRT
        ).astimezone(timezone.utc)
        session_end = min(start + MAX_HML_DURATION, day_end)
        cleanup_end = min(
            session_end + timedelta(hours=1),
            datetime.combine(
                local_start.date(), time(23, 0), tzinfo=BRT
            ).astimezone(timezone.utc),
        )
        if action == "teardown" and emergency_hml_teardown:
            if now < cleanup_end:
                raise EnvironmentWindowError(
                    "Emergency HML cleanup is allowed only after the normal cleanup window expires."
                )
            return timedelta(0)
        if action == "teardown":
            if now < session_end:
                raise EnvironmentWindowError("HML teardown cannot start before the session ends.")
            if now >= cleanup_end:
                raise EnvironmentWindowError("The HML cleanup window ends by 23:00 BRT.")
            return cleanup_end - now
        if now >= session_end:
            raise EnvironmentWindowError("The HML session ends at the earlier of five hours or 22:00 BRT.")
        return session_end - now

    _validate_prd_window(
        action=action,
        now=now,
        started_at=start,
        emergency_teardown=emergency_teardown,
    )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an environment operation window.")
    parser.add_argument("--action", choices=sorted(SUPPORTED_ACTIONS), required=True)
    parser.add_argument("--stage", choices=sorted(SUPPORTED_STAGES))
    parser.add_argument("--emergency-teardown", action="store_true")
    parser.add_argument("--emergency-hml-teardown", action="store_true")
    arguments = parser.parse_args()

    if arguments.emergency_teardown and arguments.emergency_hml_teardown:
        print("::error::Choose only one emergency teardown mode.", file=sys.stderr)
        return 1

    stage = arguments.stage or os.environ.get("ENVIRONMENT_STAGE", "")
    try:
        if arguments.emergency_hml_teardown:
            verify_emergency_hml_cleanup(
                signing_key=os.environ.get("LIFECYCLE_SESSION_SIGNING_KEY", ""),
                token=os.environ.get("LIFECYCLE_SESSION_TOKEN", ""),
                session_id=os.environ.get("ENVIRONMENT_SESSION_ID", ""),
                started_at=os.environ.get("ENVIRONMENT_WINDOW_STARTED_AT", ""),
                close_request_id=os.environ.get("CLOSE_REQUEST_ID", ""),
            )
        else:
            verify_lifecycle_session(
                signing_key=os.environ.get("LIFECYCLE_SESSION_SIGNING_KEY", ""),
                token=os.environ.get("LIFECYCLE_SESSION_TOKEN", ""),
                session_mode=os.environ.get("SESSION_MODE", ""),
                session_id=os.environ.get("ENVIRONMENT_SESSION_ID", ""),
                started_at=os.environ.get("ENVIRONMENT_WINDOW_STARTED_AT", ""),
            )
        remaining = validate_environment_window(
            active=os.environ.get("ENVIRONMENT_ACTIVE", ""),
            authorized=os.environ.get("ENVIRONMENT_WINDOW_AUTHORIZED", ""),
            session_id=os.environ.get("ENVIRONMENT_SESSION_ID", ""),
            stage=stage,
            action=arguments.action,
            started_at=os.environ.get("ENVIRONMENT_WINDOW_STARTED_AT", ""),
            now=datetime.now(timezone.utc),
            emergency_teardown=arguments.emergency_teardown,
            emergency_hml_teardown=arguments.emergency_hml_teardown,
        )
    except (EnvironmentWindowError, LifecycleSessionAuthError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1

    message = f"Environment window accepted for {stage}/{arguments.action}."
    if remaining is not None:
        message += f" {int(remaining.total_seconds())} HML seconds remain."
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
