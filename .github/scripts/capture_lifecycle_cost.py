#!/usr/bin/env python3
"""Capture a planning estimate separately from observed Cost Explorer billing."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SESSION_PATTERN = re.compile(r"^(?:hml|prd)-\d{4}-\d{2}-\d{2}$")
SPEND_WINDOW_START = date(2026, 10, 1)
GROSS_RECORD_TYPES = frozenset(
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
EXCLUDED_CREDIT_DISCOUNT_RECORD_TYPES = frozenset(
    {
        "Credit",
        "Refund",
        "Discount",
        "BundledDiscount",
        "SavingsPlanNegation",
        "EdpDiscount",
        "PrivateRateDiscount",
    }
)
OBSERVED_BILLING_SOURCE = "AWS Cost Explorer UnblendedCost grouped by SERVICE and RECORD_TYPE"


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_report(
    stage: str,
    session_id: str,
    phase: str,
    estimate: Decimal | None,
    as_of: datetime,
    expected_account_id: str,
) -> dict[str, Any]:
    return {
        "aws_account_id": expected_account_id,
        "stage": stage,
        "session_id": session_id,
        "phase": phase,
        "captured_at_utc": as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "planning_estimate": {
            "daily_floor_usd": str(estimate) if estimate is not None else None,
            "source": "operator-maintained PRD/HML lifecycle estimate",
            "type": "estimate",
            "status": "available" if estimate is not None else "unavailable",
        },
        "observed_billing": {
            "source": OBSERVED_BILLING_SOURCE,
            "type": "observed billing",
            "period_start_utc": SPEND_WINDOW_START.isoformat(),
            "period_end_exclusive_utc": as_of.date().isoformat(),
            "data_lag_note": "Cost Explorer data can lag resource usage; the guard rejects billing evidence more than three days behind the capture date.",
            "status": "unavailable",
            "reason": "No successful Cost Explorer query has been recorded.",
            "data_through_utc": None,
            "daily_totals": [],
            "group_by": ["SERVICE", "RECORD_TYPE"],
            "gross_record_types": sorted(GROSS_RECORD_TYPES),
            "positive_records_only": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("hml", "prd"), required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--estimate-daily-floor-usd", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()

    if not SESSION_PATTERN.fullmatch(arguments.session_id) or not arguments.session_id.startswith(f"{arguments.stage}-"):
        print("::error::Session ID does not match the selected stage.", file=sys.stderr)
        return 1
    if not re.fullmatch(r"[0-9]{12}", arguments.expected_account_id):
        print("::error::The expected AWS account ID is invalid.", file=sys.stderr)
        return 1
    estimate: Decimal | None
    if arguments.estimate_daily_floor_usd == "unavailable":
        estimate = None
    else:
        try:
            estimate = Decimal(arguments.estimate_daily_floor_usd)
            if not estimate.is_finite() or estimate < 0:
                raise InvalidOperation
        except InvalidOperation:
            print("::error::The lifecycle cost estimate must be a non-negative decimal USD value or unavailable.", file=sys.stderr)
            return 1

    as_of = datetime.now(timezone.utc)
    report = _base_report(
        arguments.stage,
        arguments.session_id,
        arguments.phase,
        estimate,
        as_of,
        arguments.expected_account_id,
    )
    end_date = as_of.date()
    if end_date <= SPEND_WINDOW_START:
        print("::error::The approved October 2026 spend window has not started.", file=sys.stderr)
        return 1
    start_date = SPEND_WINDOW_START
    command = [
        "aws",
        "ce",
        "get-cost-and-usage",
        "--time-period",
        f"Start={start_date.isoformat()},End={end_date.isoformat()}",
        "--granularity",
        "DAILY",
        "--metrics",
        "UnblendedCost",
        "--group-by",
        json.dumps(
            [
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "RECORD_TYPE"},
            ],
            separators=(",", ":"),
        ),
        "--output",
        "json",
        "--no-paginate",
        "--no-cli-pager",
    ]

    try:
        identity = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text", "--no-cli-pager"],
            check=True,
            capture_output=True,
            text=True,
        )
        if identity.stdout.strip() != arguments.expected_account_id:
            raise subprocess.CalledProcessError(1, "aws sts get-caller-identity")
        response = subprocess.run(command, check=True, capture_output=True, text=True)
        data = json.loads(response.stdout)
        if not isinstance(data, dict) or data.get("NextPageToken") or data.get("nextPageToken"):
            raise ValueError("Cost Explorer results were paginated or malformed.")
        results = data.get("ResultsByTime")
        if not isinstance(results, list):
            raise ValueError("Cost Explorer daily results are missing.")

        daily_totals: list[dict[str, str]] = []
        expected_day = start_date
        for period in results:
            if not isinstance(period, dict):
                raise ValueError("Cost Explorer returned a malformed daily period.")
            period_range = period.get("TimePeriod")
            if not isinstance(period_range, dict):
                raise ValueError("Cost Explorer returned a malformed daily date range.")
            day_start = date.fromisoformat(period_range.get("Start", ""))
            day_end = date.fromisoformat(period_range.get("End", ""))
            if day_start != expected_day or day_end != day_start + timedelta(days=1):
                raise ValueError("Cost Explorer daily periods are missing, duplicated, or out of order.")
            if day_end > end_date:
                raise ValueError("Cost Explorer returned a daily period beyond the requested range.")
            groups = period.get("Groups")
            if not isinstance(groups, list):
                raise ValueError("Cost Explorer returned missing or malformed SERVICE/RECORD_TYPE groups.")
            daily_gross = Decimal("0")
            for group in groups:
                if not isinstance(group, dict):
                    raise ValueError("Cost Explorer returned a malformed grouped cost record.")
                keys = group.get("Keys")
                metrics = group.get("Metrics")
                if not isinstance(keys, list) or len(keys) != 2 or not all(isinstance(key, str) for key in keys):
                    raise ValueError("Cost Explorer returned malformed SERVICE/RECORD_TYPE group keys.")
                if not isinstance(metrics, dict):
                    raise ValueError("Cost Explorer returned malformed grouped cost metrics.")
                metric = metrics.get("UnblendedCost")
                if not isinstance(metric, dict) or metric.get("Unit") != "USD":
                    raise ValueError("Cost Explorer returned a missing or unexpected currency.")
                amount = Decimal(str(metric.get("Amount", "")))
                if not amount.is_finite():
                    raise ValueError("Cost Explorer returned a malformed gross cost amount.")
                record_type = keys[1]
                if (
                    amount > 0
                    and record_type not in GROSS_RECORD_TYPES | EXCLUDED_CREDIT_DISCOUNT_RECORD_TYPES
                ):
                    raise ValueError(f"Cost Explorer returned an unrecognized positive record type: {record_type}.")
                if amount > 0 and record_type in GROSS_RECORD_TYPES:
                    daily_gross += amount
            daily_totals.append({"date": day_start.isoformat(), "amount": str(daily_gross)})
            expected_day = day_end

        if expected_day != end_date or not daily_totals:
            raise ValueError("Cost Explorer did not return complete daily spend-window evidence.")
        report["observed_billing"].update(
            {
                "status": "available",
                "reason": None,
                "currency": "USD",
                "data_through_utc": daily_totals[-1]["date"],
                "daily_totals": daily_totals,
                "query_period_days": len(daily_totals),
                "group_by": ["SERVICE", "RECORD_TYPE"],
                "gross_record_types": sorted(GROSS_RECORD_TYPES),
                "positive_records_only": True,
                "credit_refund_filter": "excluded-by-positive-record-aggregation",
                "cost_explorer_api_requests": 1,
            }
        )
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        InvalidOperation,
        AttributeError,
        TypeError,
        ValueError,
    ):
        report["observed_billing"]["reason"] = (
            "Cost Explorer identity, expected account, permissions, or billing query was unavailable."
        )
        _write_report(Path(arguments.output), report)
        print(
            "::error::Cost Explorer billing evidence is unavailable. The lifecycle must fail closed; no billing values were inferred.",
            file=sys.stderr,
        )
        return 1

    _write_report(Path(arguments.output), report)
    print(
        f"Recorded separate planning estimate and observed billing evidence for {arguments.session_id} ({arguments.phase})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
