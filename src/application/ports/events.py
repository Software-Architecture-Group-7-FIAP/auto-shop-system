from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ServiceOrderProcessingFailed:
    event_id: str
    occurred_at: datetime
    request_id: str
    service_order_id: int
    severity: str = "error"
    event_type: str = "ServiceOrderProcessingFailed"
    event_version: int = 1


class ServiceOrderEventPublisher(Protocol):
    def publish(self, event: ServiceOrderProcessingFailed) -> None:
        ...
