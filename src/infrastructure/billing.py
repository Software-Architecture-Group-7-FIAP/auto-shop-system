from datetime import UTC, datetime


class SystemBillingClock:
    def now(self) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
