from datetime import datetime
from typing import Protocol


class BillingClock(Protocol):
    def now(self) -> datetime:
        ...
