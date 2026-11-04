import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.domain.enums import ServiceOrderStatus
from src.infrastructure.observability.business_telemetry import (
    ServiceOrderCreatedEvent,
    ServiceOrderFailureEvent,
    ServiceOrderStatusDurationEvent,
    discard_pending_business_events,
    emit_service_order_failure,
    flush_pending_business_events,
    queue_business_event,
)
from src.infrastructure.observability.json_logging import JsonLogFormatter
from src.infrastructure.observability.context import correlation_id_var, service_order_id_var


class _Session:
    def __init__(self) -> None:
        self.info: dict[str, object] = {}


def _capture_business_logs():
    payloads: list[dict[str, object]] = []
    formatter = JsonLogFormatter("test", linking_metadata_provider=lambda: {})

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            payloads.append(json.loads(formatter.format(record)))

    logger = logging.getLogger("src.observability.business")
    previous_level = logger.level
    previous_disabled = logger.disabled
    logger.setLevel(logging.INFO)
    logger.disabled = False
    handler = _Capture()
    logger.addHandler(handler)
    return logger, handler, payloads, previous_level, previous_disabled


def _restore_business_logs(logger, handler, previous_level, previous_disabled):
    logger.removeHandler(handler)
    logger.setLevel(previous_level)
    logger.disabled = previous_disabled


def test_success_events_are_emitted_only_after_flush_and_rollback_discards_them():
    session = _Session()
    logger, handler, payloads, previous_level, previous_disabled = _capture_business_logs()
    event = ServiceOrderCreatedEvent(
        occurred_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        status=ServiceOrderStatus.AGUARDANDO_INICIO,
    )
    try:
        queue_business_event(session, event)
        assert payloads == []

        discard_pending_business_events(session)
        flush_pending_business_events(session)
        assert payloads == []

        queue_business_event(session, event)
        flush_pending_business_events(session)
    finally:
        _restore_business_logs(logger, handler, previous_level, previous_disabled)

    assert len(payloads) == 1
    assert payloads[0]["event"] == "ServiceOrderCreated"


def test_status_duration_event_has_bounded_allowlisted_payload():
    logger, handler, payloads, previous_level, previous_disabled = _capture_business_logs()
    started = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    event = ServiceOrderStatusDurationEvent.from_interval(
        status=ServiceOrderStatus.EM_DIAGNOSTICO,
        to_status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
        transition_type="budget_submitted",
        entered_at=started,
        occurred_at=started + timedelta(minutes=45),
    )
    try:
        queue_business_event(_session := _Session(), event)
        flush_pending_business_events(_session)
    finally:
        _restore_business_logs(logger, handler, previous_level, previous_disabled)

    payload = payloads[0]
    assert payload["event"] == "ServiceOrderStatusDuration"
    assert payload["status"] == ServiceOrderStatus.EM_DIAGNOSTICO.value
    assert payload["to_status"] == ServiceOrderStatus.AGUARDANDO_APROVACAO.value
    assert payload["transition_type"] == "budget_submitted"
    assert payload["duration_ms"] == 2_700_000
    assert payload["duration_unit"] == "milliseconds"
    assert "service_order_id" not in payload
    assert "correlation_id" not in payload


def test_failure_event_uses_closed_taxonomy_and_only_approved_identifier():
    logger, handler, payloads, previous_level, previous_disabled = _capture_business_logs()
    try:
        emit_service_order_failure(
            ServiceOrderFailureEvent(
                service_order_id=17,
                failure_type="processing_error",
                subsystem="service_order",
            )
        )
    finally:
        _restore_business_logs(logger, handler, previous_level, previous_disabled)

    payload = payloads[0]
    assert payload["event"] == "ServiceOrderProcessingFailure"
    assert payload["service_order_id"] == 17
    assert payload["failure_type"] == "processing_error"
    assert payload["subsystem"] == "service_order"
    assert "message" in payload
    assert "exception" not in payload
    assert "stack_trace" not in payload


def test_business_event_contract_suppresses_hostile_ambient_context():
    logger, handler, payloads, previous_level, previous_disabled = _capture_business_logs()
    correlation = correlation_id_var.set("CPF 529.982.247-25 customer@example.com")
    order = service_order_id_var.set(999_999)
    try:
        emit_service_order_failure(
            ServiceOrderFailureEvent(
                service_order_id=23,
                failure_type="integration_error",
                subsystem="event_bus",
            )
        )
    finally:
        correlation_id_var.reset(correlation)
        service_order_id_var.reset(order)
        _restore_business_logs(logger, handler, previous_level, previous_disabled)

    serialized = json.dumps(payloads, ensure_ascii=False)
    assert "529.982.247-25" not in serialized
    assert "customer@example.com" not in serialized
    assert "correlation_id" not in payloads[0]
    assert payloads[0]["service_order_id"] == 23
    prohibited = {
        "customer_id",
        "vehicle_id",
        "budget_id",
        "actor_id",
        "mechanic_name",
        "reason",
        "payload",
        "headers",
        "authorization",
        "cookie",
    }
    assert prohibited.isdisjoint(payloads[0])


@pytest.mark.parametrize(
    ("event", "message"),
    (
        (
            ServiceOrderStatusDurationEvent(
                status=ServiceOrderStatus.EM_DIAGNOSTICO,
                to_status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
                transition_type="CPF 529.982.247-25",
                duration_ms=1,
                occurred_at=datetime.now(timezone.utc),
            ),
            "transition type",
        ),
        (
            ServiceOrderStatusDurationEvent(
                status=ServiceOrderStatus.EM_DIAGNOSTICO,
                to_status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
                transition_type="budget_submitted",
                duration_ms=-1,
                occurred_at=datetime.now(timezone.utc),
            ),
            "duration",
        ),
        (
            ServiceOrderFailureEvent(
                service_order_id=True,
                failure_type="processing_error",
                subsystem="service_order",
            ),
            "identifier",
        ),
        (
            ServiceOrderFailureEvent(
                service_order_id=1,
                failure_type="processing_error",
                subsystem="service_order",
                event_id="customer@example.com",
            ),
            "event identifier",
        ),
    ),
)
def test_direct_construction_cannot_bypass_business_event_validation(event, message):
    with pytest.raises(ValueError, match=message):
        event.attributes()


def test_malformed_queued_event_cannot_change_committed_outcome():
    session = _Session()
    queue_business_event(
        session,
        ServiceOrderStatusDurationEvent(
            status=ServiceOrderStatus.EM_DIAGNOSTICO,
            to_status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
            transition_type="free text customer@example.com",
            duration_ms=1,
            occurred_at=datetime.now(timezone.utc),
        ),
    )

    flush_pending_business_events(session)

    assert session.info == {}


def test_service_order_business_runbook_documents_queries_units_and_privacy():
    root = Path(__file__).resolve().parents[3]
    content = (
        root / "docs" / "observability" / "new-relic-service-order-events.md"
    ).read_text(encoding="utf-8")
    lowered = content.lower()

    assert "serviceordercreated" in lowered
    assert "serviceorderstatusduration" in lowered
    assert "serviceorderprocessingfailure" in lowered
    assert "duration_unit=milliseconds" in lowered
    assert "facet status" in lowered
    assert "facet failure_type, subsystem" in lowered
    assert "cpf" in lowered and "cnpj" in lowered
    assert "2026-10-31" in content
