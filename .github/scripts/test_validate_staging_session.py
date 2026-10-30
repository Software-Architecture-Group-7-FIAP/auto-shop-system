import unittest
from datetime import datetime, timedelta, timezone

from validate_staging_session import StagingSessionError, validate_staging_session


class ValidateStagingSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)

    def validate(self, *, started_at: str, minimum_remaining_seconds: int = 0) -> None:
        validate_staging_session(
            active="true",
            authorized="true",
            session_id="phase-3-demo",
            started_at=started_at,
            now=self.now,
            minimum_remaining_seconds=minimum_remaining_seconds,
        )

    def test_accepts_active_authorized_session_within_five_hours(self) -> None:
        self.validate(started_at="2026-10-28T08:00:00Z", minimum_remaining_seconds=1800)

    def test_rejects_inactive_session(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "STAGING_ACTIVE"):
            validate_staging_session(
                active="false",
                authorized="true",
                session_id="phase-3-demo",
                started_at="2026-10-28T11:00:00Z",
                now=self.now,
            )

    def test_rejects_session_without_explicit_authorization(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "STAGING_SESSION_AUTHORIZED"):
            validate_staging_session(
                active="true",
                authorized="false",
                session_id="phase-3-demo",
                started_at="2026-10-28T11:00:00Z",
                now=self.now,
            )

    def test_rejects_missing_session_id(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "STAGING_SESSION_ID"):
            validate_staging_session(
                active="true",
                authorized="true",
                session_id="",
                started_at="2026-10-28T11:00:00Z",
                now=self.now,
            )

    def test_rejects_missing_start_time(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "STAGING_SESSION_STARTED_AT"):
            self.validate(started_at="")

    def test_rejects_malformed_or_non_utc_start_time(self) -> None:
        for started_at in (
            "2026-10-28T11:00:00+00:00",
            "2026-10-28 11:00:00Z",
            "2026-02-30T11:00:00Z",
        ):
            with self.subTest(started_at=started_at):
                with self.assertRaisesRegex(StagingSessionError, "STAGING_SESSION_STARTED_AT"):
                    self.validate(started_at=started_at)

    def test_rejects_future_start_time(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "future"):
            self.validate(started_at="2026-10-28T12:00:01Z")

    def test_rejects_session_at_five_hour_limit(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "five-hour limit"):
            self.validate(started_at="2026-10-28T07:00:00Z")

    def test_rejects_session_with_insufficient_time_for_job(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "remaining session time"):
            self.validate(
                started_at="2026-10-28T07:29:59Z",
                minimum_remaining_seconds=1800,
            )

    def test_accepts_exact_minimum_remaining_time(self) -> None:
        self.validate(
            started_at="2026-10-28T07:30:00Z",
            minimum_remaining_seconds=1800,
        )

    def test_rejects_naive_clock(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "UTC-aware"):
            validate_staging_session(
                active="true",
                authorized="true",
                session_id="phase-3-demo",
                started_at="2026-10-28T11:00:00Z",
                now=datetime(2026, 10, 28, 12, 0, 0),
            )

    def test_rejects_negative_remaining_time_requirement(self) -> None:
        with self.assertRaisesRegex(StagingSessionError, "non-negative"):
            self.validate(
                started_at="2026-10-28T11:00:00Z",
                minimum_remaining_seconds=-1,
            )


if __name__ == "__main__":
    unittest.main()
