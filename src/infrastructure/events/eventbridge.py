import json
from typing import Any, Protocol

from src.application.ports.events import ServiceOrderProcessingFailed


class EventBridgeClient(Protocol):
    def put_events(self, *, Entries: list[dict[str, Any]]) -> dict[str, Any]:
        ...


class EventPublisherNotConfiguredError(RuntimeError):
    """Raised when failure events cannot be routed to a configured event bus."""


class EventBridgeServiceOrderEventPublisher:
    def __init__(
        self,
        event_bus_name: str | None,
        client: EventBridgeClient | None = None,
    ):
        self.event_bus_name = event_bus_name
        self.client = client

    def publish(self, event: ServiceOrderProcessingFailed) -> None:
        if not self.event_bus_name:
            raise EventPublisherNotConfiguredError

        client = self.client or self._create_client()
        response = client.put_events(
            Entries=[
                {
                    "EventBusName": self.event_bus_name,
                    "Source": "auto-shop.service-orders",
                    "DetailType": event.event_type,
                    "Time": event.occurred_at,
                    "Detail": json.dumps(
                        {
                            "event_id": event.event_id,
                            "event_type": event.event_type,
                            "event_version": event.event_version,
                            "occurred_at": event.occurred_at.isoformat(),
                            "request_id": event.request_id,
                            "service_order_id": event.service_order_id,
                            "severity": event.severity,
                        },
                        separators=(",", ":"),
                    ),
                }
            ]
        )
        if response.get("FailedEntryCount", 0):
            raise RuntimeError("EventBridge rejected a service order failure event")

    @staticmethod
    def _create_client() -> EventBridgeClient:
        import boto3
        from botocore.config import Config

        return boto3.client(
            "events",
            config=Config(
                connect_timeout=1,
                read_timeout=2,
                retries={"max_attempts": 1, "mode": "standard"},
            ),
        )
