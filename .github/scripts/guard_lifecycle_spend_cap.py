#!/usr/bin/env python3
"""Fail closed unless fresh gross-cost evidence stays under the approved cap."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


CAP_WINDOW_START = date(2026, 10, 1)
CAP_WINDOW_END = date(2026, 11, 5)
CAP_WINDOW_END_EXCLUSIVE = CAP_WINDOW_END + timedelta(days=1)
HML_LAST_DAY = date(2026, 10, 31)
PRD_FIRST_DAY = date(2026, 11, 1)
MAX_EVIDENCE_AGE = timedelta(hours=1)
MAX_BILLING_LAG_DAYS = 3
COST_EXPLORER_REQUEST_USD = Decimal("0.01")
REQUESTS_PER_SESSION = 2
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SESSION_PATTERN = re.compile(r"^(hml|prd)-(\d{4}-\d{2}-\d{2})$")
CENT = Decimal("0.01")
BRT = ZoneInfo("America/Sao_Paulo")
GROSS_RECORD_TYPES = sorted(
    {
        "Usage",
        "DiscountedUsage",
        "SavingsPlanCoveredUsage",
        "Fee",
        "RecurringFee",
        "RIFee",
        "SavingsPlanRecurringFee",
        "SavingsPlanUpfrontFee",
        "Tax",
        "Support",
    }
)
USAGE_RATE_DAYS = 7


class SpendCapError(ValueError):
    """Raised when cost evidence cannot safely authorize an environment session."""


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise SpendCapError(f"{field} is missing or malformed.")
    try:
        parsed = datetime.strptime(value, UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise SpendCapError(f"{field} is missing or malformed.") from error
    if parsed.strftime(UTC_FORMAT) != value:
        raise SpendCapError(f"{field} is missing or malformed.")
    return parsed


def _parse_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise SpendCapError(f"{field} is missing or malformed.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise SpendCapError(f"{field} is missing or malformed.") from error
    if parsed.isoformat() != value:
        raise SpendCapError(f"{field} is missing or malformed.")
    return parsed


def _amount(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise SpendCapError(f"{field} amount is missing or malformed.")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise SpendCapError(f"{field} amount is missing or malformed.") from error
    if not result.is_finite() or result < 0:
        raise SpendCapError(f"{field} amount must be a finite, non-negative USD value.")
    return result


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _session_query_slots(first_day: date) -> int:
    """Reserve two Cost Explorer calls for each eligible stage/date still unbilled."""
    if first_day > CAP_WINDOW_END:
        return 0
    hml_start = max(first_day, CAP_WINDOW_START)
    hml_end = min(CAP_WINDOW_END, HML_LAST_DAY)
    hml_days = max((hml_end - hml_start).days + 1, 0)

    prd_start = max(first_day, PRD_FIRST_DAY)
    prd_days = max((CAP_WINDOW_END - prd_start).days + 1, 0)
    return hml_days + prd_days


def evaluate_spend_cap(
    report: dict[str, Any],
    *,
    now: datetime,
    expected_account_id: str,
    expected_stage: str,
    expected_session_id: str,
) -> dict[str, Any]:
    """Compute a conservative projection from verified Cost Explorer report data."""
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise SpendCapError("The spend-cap evaluation time must be UTC-aware.")
    if not isinstance(report, dict):
        raise SpendCapError("The lifecycle cost evidence must be a JSON object.")
    session_day_now = now.astimezone(BRT).date()
    if session_day_now < CAP_WINDOW_START or session_day_now > CAP_WINDOW_END:
        raise SpendCapError("The approved spend-cap cutoff has expired or is not active.")
    if not re.fullmatch(r"[0-9]{12}", expected_account_id):
        raise SpendCapError("The expected AWS account ID is missing or malformed.")
    if report.get("aws_account_id") != expected_account_id:
        raise SpendCapError("Cost evidence is missing or belongs to an unexpected AWS account.")
    if report.get("stage") != expected_stage or report.get("session_id") != expected_session_id:
        raise SpendCapError("Cost evidence does not match the requested lifecycle session.")
    match = SESSION_PATTERN.fullmatch(expected_session_id)
    if match is None or match.group(1) != expected_stage:
        raise SpendCapError("The requested lifecycle session ID or stage is malformed.")
    session_day = _parse_date(match.group(2), "session date")
    if not CAP_WINDOW_START <= session_day <= CAP_WINDOW_END:
        raise SpendCapError("The requested lifecycle session is outside the approved spend-cap cutoff.")
    if (expected_stage == "hml" and session_day > HML_LAST_DAY) or (
        expected_stage == "prd" and session_day < PRD_FIRST_DAY
    ):
        raise SpendCapError("The requested lifecycle session date is outside the approved stage window.")
    if session_day != session_day_now:
        raise SpendCapError("The requested lifecycle session date is not today's BRT date.")
    if report.get("phase") != "before":
        raise SpendCapError("Only a fresh pre-session cost report can authorize a session.")

    captured_at = _parse_utc(report.get("captured_at_utc"), "captured_at_utc")
    evidence_age = now - captured_at
    if evidence_age < timedelta(0) or evidence_age > MAX_EVIDENCE_AGE:
        raise SpendCapError("Cost evidence is not fresh; capture must be less than one hour old.")

    estimate = report.get("planning_estimate")
    if not isinstance(estimate, dict) or estimate.get("status") != "available":
        raise SpendCapError("An explicit per-day cost floor is required.")
    daily_floor = _amount(estimate.get("daily_floor_usd"), "planning estimate")

    billing = report.get("observed_billing")
    if not isinstance(billing, dict) or billing.get("status") != "available":
        raise SpendCapError("Fresh Cost Explorer billing evidence is unavailable.")
    if (
        billing.get("source")
        != "AWS Cost Explorer UnblendedCost grouped by SERVICE and RECORD_TYPE"
        or billing.get("currency") != "USD"
        or billing.get("group_by") != ["SERVICE", "RECORD_TYPE"]
        or billing.get("gross_record_types") != GROSS_RECORD_TYPES
        or billing.get("positive_records_only") is not True
    ):
        raise SpendCapError(
            "Gross Cost Explorer source, record grouping, USD currency, or positive-only aggregation cannot be verified."
        )
    if billing.get("period_start_utc") != CAP_WINDOW_START.isoformat():
        raise SpendCapError("The observed billing window does not start at the approved cap window.")
    if billing.get("period_end_exclusive_utc") != captured_at.date().isoformat():
        raise SpendCapError("The observed billing window does not match the capture date.")

    data_through = _parse_date(billing.get("data_through_utc"), "data_through_utc")
    if data_through < CAP_WINDOW_START or data_through >= captured_at.date():
        raise SpendCapError("The latest Cost Explorer billing date is missing or invalid.")
    if (captured_at.date() - data_through).days > MAX_BILLING_LAG_DAYS:
        raise SpendCapError("Cost Explorer billing evidence is stale.")

    raw_daily_totals = billing.get("daily_totals")
    if not isinstance(raw_daily_totals, list) or not raw_daily_totals:
        raise SpendCapError("Complete daily billing dates are required to calculate a usage rate.")

    daily_totals: dict[date, Decimal] = {}
    for item in raw_daily_totals:
        if not isinstance(item, dict):
            raise SpendCapError("A daily billing record is malformed.")
        billing_day = _parse_date(item.get("date"), "daily billing date")
        if billing_day in daily_totals:
            raise SpendCapError("Cost Explorer daily billing dates must be unique.")
        daily_totals[billing_day] = _amount(item.get("amount"), "daily billing")

    expected_days: list[date] = []
    current_day = CAP_WINDOW_START
    while current_day <= data_through:
        expected_days.append(current_day)
        current_day += timedelta(days=1)
    if sorted(daily_totals) != expected_days:
        raise SpendCapError("Cost Explorer daily billing dates are incomplete or out of range.")

    recent_days = expected_days[-USAGE_RATE_DAYS:]
    if len(recent_days) != USAGE_RATE_DAYS:
        raise SpendCapError("At least seven complete billing days are required for a usage-derived rate.")
    observed_gross = sum((daily_totals[day] for day in expected_days), Decimal("0"))
    usage_daily_rate = max(daily_totals[day] for day in recent_days)
    projected_daily_rate = max(daily_floor, usage_daily_rate)
    projection_days = (CAP_WINDOW_END - data_through).days
    query_slots = _session_query_slots(data_through + timedelta(days=1))
    if session_day <= data_through:
        query_slots += 1
    query_count = query_slots * REQUESTS_PER_SESSION
    query_reserve = COST_EXPLORER_REQUEST_USD * query_count
    projected_gross = (
        observed_gross
        + projected_daily_rate * projection_days
        + query_reserve
    ).quantize(CENT, rounding=ROUND_CEILING)
    cap = Decimal("100.00")
    status = "allowed" if projected_gross <= cap else "blocked"

    return {
        "status": status,
        "cap_usd": _decimal_text(cap),
        "window_start_utc": CAP_WINDOW_START.isoformat(),
        "window_end_inclusive_utc": CAP_WINDOW_END.isoformat(),
        "cost_explorer_window_end_exclusive_utc": CAP_WINDOW_END_EXCLUSIVE.isoformat(),
        "captured_at_utc": captured_at.strftime(UTC_FORMAT),
        "billing_data_through_utc": data_through.isoformat(),
        "observed_gross_usd": _decimal_text(observed_gross),
        "configured_daily_floor_usd": _decimal_text(daily_floor),
        "usage_derived_daily_usd": _decimal_text(usage_daily_rate),
        "usage_rate_method": "maximum gross cost among trailing seven complete billing days",
        "projected_daily_usd": _decimal_text(projected_daily_rate),
        "projection_days": projection_days,
        "projected_unbilled_gross_usd": _decimal_text(projected_daily_rate * projection_days),
        "maximum_future_sessions": query_slots,
        "requests_per_session": REQUESTS_PER_SESSION,
        "reserved_cost_explorer_requests": query_count,
        "cost_explorer_request_unit_usd": _decimal_text(COST_EXPLORER_REQUEST_USD),
        "reserved_cost_explorer_queries_usd": _decimal_text(query_reserve),
        "projected_gross_through_cutoff_usd": _decimal_text(projected_gross),
        "headroom_usd": _decimal_text(cap - projected_gross),
        "evaluated_at_utc": now.strftime(UTC_FORMAT),
    }


def _load_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SpendCapError("The lifecycle cost evidence file is missing or invalid JSON.") from error
    if not isinstance(report, dict):
        raise SpendCapError("The lifecycle cost evidence must be a JSON object.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--window-end-inclusive", required=True)
    parser.add_argument("--now-utc", help=argparse.SUPPRESS)
    arguments = parser.parse_args()

    if arguments.window_end_inclusive != CAP_WINDOW_END.isoformat():
        print("::error::The lifecycle spend-cap cutoff must be 2026-11-05.", file=sys.stderr)
        return 1
    try:
        now = (
            _parse_utc(arguments.now_utc, "--now-utc")
            if arguments.now_utc
            else datetime.now(timezone.utc)
        )
        report_path = Path(arguments.input)
        report = _load_report(report_path)
        projection = evaluate_spend_cap(
            report,
            now=now,
            expected_account_id=arguments.expected_account_id,
            expected_stage=arguments.stage,
            expected_session_id=arguments.session_id,
        )
    except SpendCapError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1

    report["spend_cap_projection"] = projection
    try:
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"::error::The spend-cap projection could not be recorded: {error}", file=sys.stderr)
        return 1
    print(
        "Spend-cap projection: "
        f"${projection['projected_gross_through_cutoff_usd']} of ${projection['cap_usd']} "
        f"through {projection['window_end_inclusive_utc']} ("
        f"{projection['reserved_cost_explorer_requests']} Cost Explorer requests reserved)."
    )
    if projection["status"] != "allowed":
        print("::error::The projected gross AWS spend exceeds the authorized US$100 cap.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
