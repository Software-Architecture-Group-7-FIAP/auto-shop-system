import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from validate_environment_window import (
    EnvironmentWindowError,
    validate_environment_window,
)


class ValidateEnvironmentWindowTests(unittest.TestCase):
    def validate(
        self,
        *,
        stage: str,
        action: str,
        now: datetime,
        started_at: str,
        emergency_teardown: bool = False,
    ) -> None:
        validate_environment_window(
            active="true",
            authorized="true",
            session_id=f"{stage}-{self.session_date(started_at)}",
            stage=stage,
            action=action,
            started_at=started_at,
            now=now,
            emergency_teardown=emergency_teardown,
        )

    @staticmethod
    def session_date(started_at: str) -> str:
        start = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        return start.astimezone(ZoneInfo("America/Sao_Paulo")).date().isoformat()

    def test_accepts_prd_start_at_0600_brt_from_november_1(self) -> None:
        self.validate(
            stage="prd",
            action="start",
            now=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
            started_at="2026-11-01T09:00:00Z",
        )

    def test_rejects_prd_before_delivery_window(self) -> None:
        with self.assertRaisesRegex(EnvironmentWindowError, "01/11/2026"):
            self.validate(
                stage="prd",
                action="start",
                now=datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc),
                started_at="2026-10-31T09:00:00Z",
            )

    def test_rejects_prd_after_november_5(self) -> None:
        with self.assertRaisesRegex(EnvironmentWindowError, "05/11/2026"):
            self.validate(
                stage="prd",
                action="start",
                now=datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc),
                started_at="2026-11-06T09:00:00Z",
            )

    def test_accepts_health_from_0645_brt(self) -> None:
        self.validate(
            stage="prd",
            action="health",
            now=datetime(2026, 11, 2, 9, 45, tzinfo=timezone.utc),
            started_at="2026-11-02T09:00:00Z",
        )

    def test_rejects_health_before_0645_brt(self) -> None:
        with self.assertRaisesRegex(EnvironmentWindowError, "06:45"):
            self.validate(
                stage="prd",
                action="health",
                now=datetime(2026, 11, 2, 9, 44, 59, tzinfo=timezone.utc),
                started_at="2026-11-02T09:00:00Z",
            )

    def test_keeps_prd_operational_after_2130_brt(self) -> None:
        self.validate(
            stage="prd",
            action="operate",
            now=datetime(2026, 11, 2, 0, 45, tzinfo=timezone.utc),
            started_at="2026-11-01T09:00:00Z",
        )

    def test_starts_teardown_at_2200_brt(self) -> None:
        self.validate(
            stage="prd",
            action="teardown",
            now=datetime(2026, 11, 2, 1, 0, tzinfo=timezone.utc),
            started_at="2026-11-01T09:00:00Z",
        )

    def test_rejects_regular_teardown_before_2200_brt(self) -> None:
        with self.assertRaisesRegex(EnvironmentWindowError, "22:00"):
            self.validate(
                stage="prd",
                action="teardown",
                now=datetime(2026, 11, 2, 0, 59, 59, tzinfo=timezone.utc),
                started_at="2026-11-01T09:00:00Z",
            )

    def test_allows_emergency_teardown_outside_regular_window(self) -> None:
        self.validate(
            stage="prd",
            action="teardown",
            now=datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc),
            started_at="2026-11-01T09:00:00Z",
            emergency_teardown=True,
        )

    def test_accepts_hml_before_five_hour_limit(self) -> None:
        self.validate(
            stage="hml",
            action="operate",
            now=datetime(2026, 10, 30, 14, 59, 59, tzinfo=timezone.utc),
            started_at="2026-10-30T10:00:00Z",
        )

    def test_rejects_hml_at_five_hour_limit(self) -> None:
        with self.assertRaisesRegex(EnvironmentWindowError, "five hours"):
            self.validate(
                stage="hml",
                action="operate",
                now=datetime(2026, 10, 30, 15, 0, tzinfo=timezone.utc),
                started_at="2026-10-30T10:00:00Z",
            )

    def test_teardown_is_not_blocked_when_hml_session_expired(self) -> None:
        self.validate(
            stage="hml",
            action="teardown",
            now=datetime(2026, 10, 30, 15, 1, tzinfo=timezone.utc),
            started_at="2026-10-30T10:00:00Z",
        )

    def test_rejects_unauthorized_operation_but_allows_teardown(self) -> None:
        common = {
            "active": "true",
            "authorized": "false",
            "session_id": "hml-2026-10-30",
            "stage": "hml",
            "started_at": "2026-10-30T10:00:00Z",
            "now": datetime(2026, 10, 30, 15, 30, tzinfo=timezone.utc),
        }
        with self.assertRaisesRegex(EnvironmentWindowError, "authorized"):
            validate_environment_window(action="operate", **common)

        validate_environment_window(action="teardown", **common)

    def test_rejects_future_start_time(self) -> None:
        with self.assertRaisesRegex(EnvironmentWindowError, "future"):
            self.validate(
                stage="hml",
                action="operate",
                now=datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
                started_at="2026-10-30T10:00:01Z",
            )

    def test_rejects_unknown_stage_and_action(self) -> None:
        for stage, action in (("production", "operate"), ("prd", "deploy")):
            with self.subTest(stage=stage, action=action):
                with self.assertRaises(EnvironmentWindowError):
                    self.validate(
                        stage=stage,
                        action=action,
                        now=datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc),
                        started_at="2026-11-01T09:00:00Z",
                    )


if __name__ == "__main__":
    unittest.main()
