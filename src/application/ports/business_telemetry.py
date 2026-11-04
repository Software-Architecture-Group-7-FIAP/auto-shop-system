from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ServiceOrderFailureTelemetry:
    event_id: str
    occurred_at: datetime
    service_order_id: int
    failure_type: str
    subsystem: str


class ServiceOrderBusinessTelemetry(Protocol):
    def record_failure(self, event: ServiceOrderFailureTelemetry) -> None:
        ...
