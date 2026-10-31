#!/usr/bin/env python3
"""Resolve the same BRT session ID and UTC start for coordinated PRD workflows."""

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


BRT = ZoneInfo("America/Sao_Paulo")
FIRST_PRD_DAY = date(2026, 11, 1)
LAST_PRD_DAY = date(2026, 11, 5)
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
HML_LAST_DAY = date(2026, 10, 31)
AUDIT_RESERVE = timedelta(minutes=15)
TEARDOWN_MARGIN = timedelta(minutes=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("start", "teardown"), required=True)
    parser.add_argument("--stage", choices=("hml", "prd"), default="prd")
    parser.add_argument("--started-at", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--session-mode", default="")
    parser.add_argument("--cleanup-dispatch", action="store_true")
    parser.add_argument("--github-output", required=True)
    arguments = parser.parse_args()

    now = datetime.now(timezone.utc)
    local_now = now.astimezone(BRT)
    if arguments.cleanup_dispatch:
        if arguments.action != "teardown" or not arguments.session_id or not arguments.started_at:
            print("::error::Expired cleanup requires a teardown action with the ledger session ID and start time.", file=sys.stderr)
            return 1
        try:
            session_stage, session_day_text = arguments.session_id.split("-", 1)
            session_day = date.fromisoformat(session_day_text)
            local_start = datetime.strptime(arguments.started_at, UTC_FORMAT).replace(tzinfo=timezone.utc).astimezone(BRT)
        except ValueError:
            print("::error::Expired cleanup session ID or start time is invalid.", file=sys.stderr)
            return 1
        expected_start = datetime.combine(session_day, time(6, 0), tzinfo=BRT) if arguments.stage == "prd" else local_start
        cleanup_end = datetime.combine(session_day, time(23, 0), tzinfo=BRT)
        if (
            session_stage != arguments.stage
            or local_start.date() != session_day
            or local_now.date() != session_day
            or local_start.astimezone(timezone.utc).strftime(UTC_FORMAT) != arguments.started_at
            or (arguments.stage == "prd" and local_start != expected_start)
            or (arguments.stage == "hml" and not time(7, 0) <= local_start.time().replace(tzinfo=None) <= time(17, 0))
            or now < local_start + timedelta(hours=5)
            or now >= cleanup_end
        ):
            print("::error::Cleanup session is not an expired same-day lifecycle window.", file=sys.stderr)
            return 1
        session_id = arguments.session_id
        session_mode = "hml" if arguments.stage == "hml" else "prd-window"
        if arguments.session_mode and arguments.session_mode != session_mode:
            print("::error::Cleanup session_mode does not match its stage.", file=sys.stderr)
            return 1
        session_end = min(local_start + timedelta(hours=5), datetime.combine(session_day, time(22, 0), tzinfo=BRT))
    elif arguments.stage == "prd":
        if not FIRST_PRD_DAY <= local_now.date() <= LAST_PRD_DAY:
            print("::error::PRD lifecycle is authorized only from 01 through 05 November 2026 BRT.", file=sys.stderr)
            return 1
        if arguments.action == "start" and not time(6, 0) <= local_now.time().replace(tzinfo=None) < time(7, 0):
            print("::error::PRD preparation may start only from 06:00 to 07:00 BRT.", file=sys.stderr)
            return 1
        local_start = datetime.combine(local_now.date(), time(6, 0), tzinfo=BRT)
        if arguments.started_at:
            if arguments.started_at != local_start.astimezone(timezone.utc).strftime(UTC_FORMAT):
                print("::error::PRD session start is fixed at 06:00 BRT (09:00 UTC).", file=sys.stderr)
                return 1
        session_end = min(
            local_start + timedelta(hours=5),
            datetime.combine(local_now.date(), time(22, 0), tzinfo=BRT),
        )
        cleanup_end = datetime.combine(local_now.date(), time(23, 0), tzinfo=BRT)
        session_mode = "prd-window"
        if arguments.session_mode and arguments.session_mode != session_mode:
            print("::error::session_mode does not match PRD.", file=sys.stderr)
            return 1
        if arguments.action == "teardown" and not local_start <= local_now < cleanup_end:
            print("::error::PRD close is allowed after session start and before the 23:00 BRT same-day cutoff.", file=sys.stderr)
            return 1
    else:
        session_mode = "hml"
        if local_now.date() > HML_LAST_DAY:
            print("::error::HML lifecycle is authorized only through 31 October 2026 BRT.", file=sys.stderr)
            return 1
        if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
            print("::error::HML has no scheduled lifecycle; dispatch the central workflow manually.", file=sys.stderr)
            return 1
        if arguments.started_at:
            try:
                local_start = datetime.strptime(arguments.started_at, UTC_FORMAT).replace(tzinfo=timezone.utc).astimezone(BRT)
            except ValueError:
                print("::error::HML started_at must use UTC format YYYY-MM-DDTHH:MM:SSZ.", file=sys.stderr)
                return 1
            if local_start.astimezone(timezone.utc).strftime(UTC_FORMAT) != arguments.started_at:
                print("::error::HML started_at must use UTC format YYYY-MM-DDTHH:MM:SSZ.", file=sys.stderr)
                return 1
        else:
            local_start = datetime.combine(local_now.date(), time(17, 0), tzinfo=BRT)
        if local_start.date() != local_now.date():
            print("::error::HML session start must use today's BRT date.", file=sys.stderr)
            return 1
        local_start_time = local_start.time().replace(tzinfo=None)
        if not time(7, 0) <= local_start_time <= time(17, 0):
            print("::error::HML sessions must start between 07:00 and 17:00 BRT.", file=sys.stderr)
            return 1
        session_end = min(
            local_start + timedelta(hours=5),
            datetime.combine(local_start.date(), time(22, 0), tzinfo=BRT),
        )
        cleanup_end = datetime.combine(local_start.date(), time(23, 0), tzinfo=BRT)
        if arguments.action == "start" and not local_start <= local_now < session_end:
            print("::error::HML opening must be invoked during the chosen five-hour BRT window.", file=sys.stderr)
            return 1
        if arguments.session_mode and arguments.session_mode != session_mode:
            print("::error::session_mode does not match HML.", file=sys.stderr)
            return 1
        if arguments.action == "teardown" and not local_start <= local_now < cleanup_end:
            print("::error::HML close is allowed after session start and before its cleanup deadline; expired sessions use daily cleanup.", file=sys.stderr)
            return 1

    if not arguments.cleanup_dispatch:
        session_id = f"{arguments.stage}-{local_now.date().isoformat()}"
    if arguments.stage == "hml" and arguments.action == "teardown" and not arguments.cleanup_dispatch:
        if not arguments.started_at or not arguments.session_id:
            print("::error::HML teardown requires the coordinator's session_id and started_at.", file=sys.stderr)
            return 1
    if arguments.session_id and arguments.session_id != session_id:
        print("::error::The provided session_id does not match the current BRT session date.", file=sys.stderr)
        return 1
    started_at = local_start.astimezone(timezone.utc).strftime(UTC_FORMAT)
    if arguments.cleanup_dispatch:
        audit_start = cleanup_end - AUDIT_RESERVE
    else:
        audit_start = cleanup_end - AUDIT_RESERVE
    teardown_deadline = audit_start - TEARDOWN_MARGIN
    with open(arguments.github_output, "a", encoding="utf-8") as output_file:
        output_file.write(f"stage={arguments.stage}\n")
        output_file.write(f"session_id={session_id}\n")
        output_file.write(f"started_at={started_at}\n")
        output_file.write(f"session_mode={session_mode}\n")
        output_file.write(f"session_end_utc={session_end.astimezone(timezone.utc).strftime(UTC_FORMAT)}\n")
        output_file.write(f"cleanup_end_utc={cleanup_end.astimezone(timezone.utc).strftime(UTC_FORMAT)}\n")
        output_file.write(
            f"teardown_deadline_utc={teardown_deadline.astimezone(timezone.utc).strftime(UTC_FORMAT)}\n"
        )
        output_file.write(f"audit_start_utc={audit_start.astimezone(timezone.utc).strftime(UTC_FORMAT)}\n")
        output_file.write(f"teardown_allowed={str(now < teardown_deadline).lower()}\n")
        health_check = datetime.combine(local_now.date(), time(6, 45), tzinfo=BRT).astimezone(timezone.utc)
        output_file.write(f"health_at_utc={health_check.strftime(UTC_FORMAT)}\n")
        health_deadline = datetime.combine(local_now.date(), time(7, 0), tzinfo=BRT).astimezone(timezone.utc)
        output_file.write(f"health_deadline_utc={health_deadline.strftime(UTC_FORMAT)}\n")
        health_alert_deadline = datetime.combine(local_now.date(), time(7, 0), tzinfo=BRT).astimezone(timezone.utc)
        output_file.write(f"health_alert_deadline_utc={health_alert_deadline.strftime(UTC_FORMAT)}\n")
        if arguments.action == "teardown":
            work_deadline = teardown_deadline
        elif arguments.stage == "prd":
            work_deadline = health_check
        else:
            work_deadline = session_end
        output_file.write(f"work_deadline_utc={work_deadline.astimezone(timezone.utc).strftime(UTC_FORMAT)}\n")

    print(f"Resolved {session_id} ({session_mode}), started at {started_at}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
