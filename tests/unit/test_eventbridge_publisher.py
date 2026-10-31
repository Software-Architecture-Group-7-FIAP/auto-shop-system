import json
from datetime import datetime, timezone

import pytest

from src.application.ports.events import ServiceOrderProcessingFailed
from src.infrastructure.events.eventbridge import (
    EventBridgeServiceOrderEventPublisher,
    EventPublisherNotConfiguredError,
)


class FakeEventBridgeClient:
    def __init__(self, response=None):
        self.entries = None
        self.response = response or {"FailedEntryCount": 0}

    def put_events(self, *, Entries):
        self.entries = Entries
        return self.response


def make_event() -> ServiceOrderProcessingFailed:
    return ServiceOrderProcessingFailed(
        event_id="event-123",
        occurred_at=datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc),
        request_id="request-123",
        service_order_id=42,
    )


def test_eventbridge_publisher_sends_only_the_versioned_minimum_payload():
    client = FakeEventBridgeClient()
    publisher = EventBridgeServiceOrderEventPublisher("staging-events", client)

    publisher.publish(make_event())

    assert client.entries is not None
    entry = client.entries[0]
    assert entry["EventBusName"] == "staging-events"
    assert entry["Source"] == "auto-shop.service-orders"
    assert entry["DetailType"] == "ServiceOrderProcessingFailed"
    assert json.loads(entry["Detail"]) == {
        "event_id": "event-123",
        "event_type": "ServiceOrderProcessingFailed",
        "event_version": 1,
        "occurred_at": "2026-10-18T12:00:00+00:00",
        "request_id": "request-123",
        "service_order_id": 42,
        "severity": "error",
    }


def test_eventbridge_publisher_fails_clearly_when_no_bus_is_configured():
    publisher = EventBridgeServiceOrderEventPublisher(None, FakeEventBridgeClient())

    with pytest.raises(EventPublisherNotConfiguredError):
        publisher.publish(make_event())


def test_eventbridge_publisher_reports_rejected_events_without_exposing_response():
    client = FakeEventBridgeClient({"FailedEntryCount": 1, "Entries": [{"ErrorMessage": "private"}]})
    publisher = EventBridgeServiceOrderEventPublisher("staging-events", client)

    with pytest.raises(RuntimeError, match="EventBridge rejected"):
        publisher.publish(make_event())
