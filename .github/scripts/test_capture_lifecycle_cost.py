import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import patch

import capture_lifecycle_cost as capture
from guard_lifecycle_spend_cap import evaluate_spend_cap


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 30, 20, 0, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)


def cost_explorer_payload(*, next_page_token: str | None = None) -> str:
    results = []
    day = date(2026, 10, 1)
    while day < date(2026, 10, 30):
        next_day = day + timedelta(days=1)
        results.append(
            {
                "TimePeriod": {"Start": day.isoformat(), "End": next_day.isoformat()},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute", "Usage"],
                        "Metrics": {"UnblendedCost": {"Amount": "1.25", "Unit": "USD"}},
                    },
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute", "Fee"],
                        "Metrics": {"UnblendedCost": {"Amount": "0.25", "Unit": "USD"}},
                    },
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute", "Credit"],
                        "Metrics": {"UnblendedCost": {"Amount": "-1.50", "Unit": "USD"}},
                    },
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute", "Refund"],
                        "Metrics": {"UnblendedCost": {"Amount": "-0.40", "Unit": "USD"}},
                    },
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute", "SavingsPlanNegation"],
                        "Metrics": {"UnblendedCost": {"Amount": "-0.25", "Unit": "USD"}},
                    },
                ],
            }
        )
        day = next_day
    result = {"ResultsByTime": results}
    if next_page_token:
        result["NextPageToken"] = next_page_token
    return json.dumps(result)


class CaptureLifecycleCostTests(unittest.TestCase):
    def run_capture(self, directory: str, response: str) -> tuple[int, list[object], dict[str, object]]:
        output = Path(directory) / "lifecycle-cost-before.json"
        calls: list[object] = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if command[1:4] == ["sts", "get-caller-identity", "--query"]:
                return CompletedProcess(command, 0, stdout="035611741563\n", stderr="")
            return CompletedProcess(command, 0, stdout=response, stderr="")

        with (
            patch.object(capture, "datetime", FrozenDateTime),
            patch.object(capture.subprocess, "run", side_effect=fake_run),
            patch.object(
                sys,
                "argv",
                [
                    "capture_lifecycle_cost.py",
                    "--stage",
                    "hml",
                    "--session-id",
                    "hml-2026-10-30",
                    "--phase",
                    "before",
                    "--expected-account-id",
                    "035611741563",
                    "--estimate-daily-floor-usd",
                    "2.00",
                    "--output",
                    str(output),
                ],
            ),
        ):
            result = capture.main()
        report = json.loads(output.read_text(encoding="utf-8"))
        return result, calls, report

    def test_captures_mtd_gross_daily_data_without_costly_pagination(self) -> None:
        with TemporaryDirectory() as directory:
            result, calls, report = self.run_capture(directory, cost_explorer_payload())

        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 2)
        command = calls[1]
        self.assertIn("Start=2026-10-01,End=2026-10-30", command)
        self.assertIn("--no-paginate", command)
        self.assertNotIn("--filter", command)
        group_by = command[command.index("--group-by") + 1]
        self.assertEqual(
            json.loads(group_by),
            [
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "RECORD_TYPE"},
            ],
        )
        billing = report["observed_billing"]
        self.assertEqual(billing["period_start_utc"], "2026-10-01")
        self.assertEqual(billing["data_through_utc"], "2026-10-29")
        self.assertEqual(len(billing["daily_totals"]), 29)
        self.assertEqual(billing["daily_totals"][0], {"date": "2026-10-01", "amount": "1.50"})
        self.assertEqual(billing["gross_record_types"], sorted(capture.GROSS_RECORD_TYPES))
        self.assertIs(billing["positive_records_only"], True)
        self.assertEqual(report["aws_account_id"], "035611741563")

        projection = evaluate_spend_cap(
            report,
            now=datetime(2026, 10, 30, 20, 15, tzinfo=timezone.utc),
            expected_account_id="035611741563",
            expected_stage="hml",
            expected_session_id="hml-2026-10-30",
        )
        self.assertEqual(projection["observed_gross_usd"], "43.50")
        self.assertEqual(projection["projected_gross_through_cutoff_usd"], "57.64")

    def test_fails_closed_if_cost_explorer_would_require_an_extra_paid_page(self) -> None:
        with TemporaryDirectory() as directory:
            result, _calls, report = self.run_capture(
                directory,
                cost_explorer_payload(next_page_token="next"),
            )

        self.assertEqual(result, 1)
        self.assertEqual(report["observed_billing"]["status"], "unavailable")

    def test_fails_closed_on_an_unrecognized_positive_record_type(self) -> None:
        payload = json.loads(cost_explorer_payload())
        first_day_groups = payload["ResultsByTime"][0]["Groups"]
        first_day_groups.append(
            {
                "Keys": ["Unexpected AWS Service", "NewChargeType"],
                "Metrics": {"UnblendedCost": {"Amount": "0.01", "Unit": "USD"}},
            }
        )
        with TemporaryDirectory() as directory:
            result, _calls, report = self.run_capture(directory, json.dumps(payload))

        self.assertEqual(result, 1)
        self.assertEqual(report["observed_billing"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
