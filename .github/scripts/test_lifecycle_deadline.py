import unittest
from datetime import datetime, timezone

from assert_lifecycle_deadline import LifecycleDeadlineError, assert_before_deadline, parse_deadline


class LifecycleDeadlineTests(unittest.TestCase):
    def test_deadline_accepts_time_before_cutoff(self) -> None:
        deadline = parse_deadline("2026-11-01T01:40:00Z")
        assert_before_deadline(deadline, datetime(2026, 11, 1, 1, 39, 59, tzinfo=timezone.utc))

    def test_deadline_rejects_exact_cutoff_and_later_time(self) -> None:
        deadline = parse_deadline("2026-11-01T01:40:00Z")
        for now in (
            datetime(2026, 11, 1, 1, 40, tzinfo=timezone.utc),
            datetime(2026, 11, 1, 1, 41, tzinfo=timezone.utc),
        ):
            with self.subTest(now=now), self.assertRaisesRegex(LifecycleDeadlineError, "only the reserved audit"):
                assert_before_deadline(deadline, now)

    def test_deadline_requires_canonical_utc_timestamp(self) -> None:
        with self.assertRaisesRegex(LifecycleDeadlineError, "UTC format"):
            parse_deadline("2026-11-01T01:40:00+00:00")


if __name__ == "__main__":
    unittest.main()
