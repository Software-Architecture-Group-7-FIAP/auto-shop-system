from unittest.mock import Mock

from src.api.composition import execution
from src.infrastructure.events.eventbridge import EventBridgeServiceOrderEventPublisher


def test_execution_composition_wires_publisher_to_configured_event_bus(monkeypatch):
    monkeypatch.setattr(execution.settings, "service_order_event_bus_name", "staging-events")

    service = execution.compose_execution_service(Mock())

    assert isinstance(service.event_publisher, EventBridgeServiceOrderEventPublisher)
    assert service.event_publisher.event_bus_name == "staging-events"


def test_execution_composition_disables_publisher_without_event_bus(monkeypatch):
    monkeypatch.setattr(execution.settings, "service_order_event_bus_name", None)

    service = execution.compose_execution_service(Mock())

    assert service.event_publisher is None
