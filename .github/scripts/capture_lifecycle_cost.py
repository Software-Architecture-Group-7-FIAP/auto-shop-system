#!/usr/bin/env python3
"""Capture a planning estimate separately from observed Cost Explorer billing."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SESSION_PATTERN = re.compile(r"^(?:hml|prd)-\d{4}-\d{2}-\d{2}$")


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_report(stage: str, session_id: str, phase: str, estimate: Decimal | None, as_of: datetime) -> dict[str, Any]:
    return {
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
            "source": "AWS Cost Explorer UnblendedCost",
            "type": "observed billing",
            "period_start_utc": (as_of.date() - timedelta(days=30)).isoformat(),
            "period_end_exclusive_utc": as_of.date().isoformat(),
            "data_lag_note": "Cost Explorer data can lag resource usage; the captured billing window is not a real-time meter.",
            "status": "unavailable",
            "reason": "No successful Cost Explorer query has been recorded.",
            "services": [],
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
    report = _base_report(arguments.stage, arguments.session_id, arguments.phase, estimate, as_of)
    end_date = as_of.date()
    start_date = end_date - timedelta(days=30)
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
        "Type=DIMENSION,Key=SERVICE",
        "--output",
        "json",
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
        totals: dict[str, Decimal] = {}
        currency = "USD"
        for day in data.get("ResultsByTime", []):
            for group in day.get("Groups", []):
                keys = group.get("Keys", [])
                service = str(keys[0]) if keys else "Unknown"
                metric = group.get("Metrics", {}).get("UnblendedCost", {})
                amount = Decimal(str(metric.get("Amount", "0")))
                totals[service] = totals.get(service, Decimal("0")) + amount
                currency = str(metric.get("Unit", currency))
        report["observed_billing"].update(
            {
                "status": "available",
                "reason": None,
                "currency": currency,
                "services": [
                    {"service": service, "amount": str(amount)}
                    for service, amount in sorted(totals.items())
                ],
                "query_period_days": 30,
            }
        )
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, InvalidOperation):
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
