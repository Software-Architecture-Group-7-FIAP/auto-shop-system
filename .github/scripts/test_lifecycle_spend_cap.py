import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from guard_lifecycle_spend_cap import GROSS_RECORD_TYPES, SpendCapError, evaluate_spend_cap


class LifecycleSpendCapTests(unittest.TestCase):
    now = datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc)

    @classmethod
    def make_report(
        cls,
        *,
        daily_amount: str = "1.00",
        daily_floor: str = "2.00",
    ) -> dict[str, object]:
        days = [
            (datetime(2026, 10, 1, tzinfo=timezone.utc).date() + timedelta(days=index)).isoformat()
            for index in range(29)
        ]
        return {
            "aws_account_id": "035611741563",
            "stage": "hml",
            "session_id": "hml-2026-10-30",
            "phase": "before",
            "captured_at_utc": "2026-10-30T19:55:00Z",
            "planning_estimate": {
                "daily_floor_usd": daily_floor,
                "status": "available",
                "type": "estimate",
            },
            "observed_billing": {
                "source": "AWS Cost Explorer UnblendedCost grouped by SERVICE and RECORD_TYPE",
                "type": "observed billing",
                "status": "available",
                "currency": "USD",
                "group_by": ["SERVICE", "RECORD_TYPE"],
                "gross_record_types": GROSS_RECORD_TYPES,
                "positive_records_only": True,
                "period_start_utc": "2026-10-01",
                "period_end_exclusive_utc": "2026-10-30",
                "data_through_utc": "2026-10-29",
                "daily_totals": [
                    {"date": day, "amount": daily_amount} for day in days
                ],
            },
        }

    def evaluate(self, report: dict[str, object]) -> dict[str, object]:
        return evaluate_spend_cap(
            report,
            now=self.now,
            expected_account_id="035611741563",
            expected_stage="hml",
            expected_session_id="hml-2026-10-30",
        )

    def test_projects_mtd_gross_cost_with_maximum_of_floor_and_recent_usage_rate(self) -> None:
        projection = self.evaluate(self.make_report())

        self.assertEqual(projection["status"], "allowed")
        self.assertEqual(projection["observed_gross_usd"], "29.00")
        self.assertEqual(projection["usage_derived_daily_usd"], "1.00")
        self.assertEqual(projection["projected_daily_usd"], "2.00")
        self.assertEqual(projection["projection_days"], 7)
        self.assertEqual(projection["reserved_cost_explorer_requests"], 14)
        self.assertEqual(projection["reserved_cost_explorer_queries_usd"], "0.14")
        self.assertEqual(projection["projected_gross_through_cutoff_usd"], "43.14")

    def test_uses_gross_recent_usage_rate_when_it_exceeds_the_operator_floor(self) -> None:
        report = self.make_report(daily_amount="4.00", daily_floor="0.50")

        projection = self.evaluate(report)

        self.assertEqual(projection["projected_daily_usd"], "4.00")
        self.assertEqual(projection["projected_gross_through_cutoff_usd"], "144.14")
        self.assertEqual(projection["status"], "blocked")

    def test_projects_from_highest_complete_day_not_recent_average(self) -> None:
        report = self.make_report(daily_amount="1.00", daily_floor="0.50")
        billing = report["observed_billing"]
        assert isinstance(billing, dict)
        daily_totals = billing["daily_totals"]
        assert isinstance(daily_totals, list)
        daily_totals[-1]["amount"] = "30.00"

        projection = self.evaluate(report)

        self.assertEqual(projection["usage_derived_daily_usd"], "30.00")
        self.assertEqual(
            projection["usage_rate_method"],
            "maximum gross cost among trailing seven complete billing days",
        )
        self.assertEqual(projection["projected_daily_usd"], "30.00")
        self.assertEqual(projection["projected_gross_through_cutoff_usd"], "268.14")
        self.assertEqual(projection["status"], "blocked")

    def test_blocks_evidence_older_than_one_hour(self) -> None:
        report = self.make_report()
        report["captured_at_utc"] = "2026-10-30T18:59:59Z"

        with self.assertRaisesRegex(SpendCapError, "fresh"):
            self.evaluate(report)

    def test_blocks_missing_or_unavailable_billing_and_rate_evidence(self) -> None:
        for report in (
            {**self.make_report(), "observed_billing": {"status": "unavailable"}},
            {**self.make_report(), "planning_estimate": {"daily_floor_usd": None}},
        ):
            with self.subTest(report=report):
                with self.assertRaises(SpendCapError):
                    self.evaluate(report)

    def test_blocks_stale_billing_window_and_gaps_in_daily_evidence(self) -> None:
        stale = copy.deepcopy(self.make_report())
        stale_billing = stale["observed_billing"]
        assert isinstance(stale_billing, dict)
        stale_billing["data_through_utc"] = "2026-10-26"
        with self.assertRaisesRegex(SpendCapError, "billing evidence is stale"):
            self.evaluate(stale)

        gapped = copy.deepcopy(self.make_report())
        gapped_billing = gapped["observed_billing"]
        assert isinstance(gapped_billing, dict)
        gapped_billing["daily_totals"] = gapped_billing["daily_totals"][1:]
        with self.assertRaisesRegex(SpendCapError, "daily billing dates"):
            self.evaluate(gapped)

    def test_blocks_malformed_or_negative_cost_values(self) -> None:
        report = copy.deepcopy(self.make_report())
        billing = report["observed_billing"]
        assert isinstance(billing, dict)
        daily_totals = billing["daily_totals"]
        assert isinstance(daily_totals, list)
        daily_totals[-1]["amount"] = "NaN"

        with self.assertRaisesRegex(SpendCapError, "amount"):
            self.evaluate(report)

    def test_blocks_wrong_account_session_or_post_cap_window(self) -> None:
        wrong_account = self.make_report()
        wrong_account["aws_account_id"] = "999999999999"
        with self.assertRaisesRegex(SpendCapError, "account"):
            self.evaluate(wrong_account)

        with self.assertRaisesRegex(SpendCapError, "session"):
            evaluate_spend_cap(
                self.make_report(),
                now=self.now,
                expected_account_id="035611741563",
                expected_stage="hml",
                expected_session_id="hml-2026-10-31",
            )

        with self.assertRaisesRegex(SpendCapError, "cutoff"):
            evaluate_spend_cap(
                self.make_report(),
                now=datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc),
                expected_account_id="035611741563",
                expected_stage="hml",
                expected_session_id="hml-2026-10-30",
            )

    def test_blocks_malformed_expected_account_and_session_on_another_brt_day(self) -> None:
        with self.assertRaisesRegex(SpendCapError, "expected AWS account ID"):
            evaluate_spend_cap(
                self.make_report(),
                now=self.now,
                expected_account_id="bad-account",
                expected_stage="hml",
                expected_session_id="hml-2026-10-30",
            )

        with self.assertRaisesRegex(SpendCapError, "today's BRT date"):
            report = self.make_report()
            report["session_id"] = "hml-2026-10-31"
            evaluate_spend_cap(
                report,
                now=self.now,
                expected_account_id="035611741563",
                expected_stage="hml",
                expected_session_id="hml-2026-10-31",
            )

    def test_includes_november_5_brt_and_reserves_the_current_session_queries(self) -> None:
        report = self.make_report()
        days = [
            (datetime(2026, 10, 1, tzinfo=timezone.utc).date() + timedelta(days=index)).isoformat()
            for index in range(36)
        ]
        report["stage"] = "prd"
        report["session_id"] = "prd-2026-11-05"
        report["captured_at_utc"] = "2026-11-06T01:00:00Z"
        billing = report["observed_billing"]
        assert isinstance(billing, dict)
        billing["period_end_exclusive_utc"] = "2026-11-06"
        billing["data_through_utc"] = "2026-11-05"
        billing["daily_totals"] = [{"date": day, "amount": "1.00"} for day in days]

        projection = evaluate_spend_cap(
            report,
            now=datetime(2026, 11, 6, 1, 30, tzinfo=timezone.utc),
            expected_account_id="035611741563",
            expected_stage="prd",
            expected_session_id="prd-2026-11-05",
        )

        self.assertEqual(projection["window_end_inclusive_utc"], "2026-11-05")
        self.assertEqual(projection["cost_explorer_window_end_exclusive_utc"], "2026-11-06")
        self.assertEqual(projection["projection_days"], 0)
        self.assertEqual(projection["reserved_cost_explorer_requests"], 2)
        self.assertEqual(projection["reserved_cost_explorer_queries_usd"], "0.02")


if __name__ == "__main__":
    unittest.main()
