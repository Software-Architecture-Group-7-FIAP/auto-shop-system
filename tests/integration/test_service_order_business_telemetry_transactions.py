import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from src.domain.budget.entity import Budget
from src.domain.enums import ServiceOrderStatus
from src.domain.service_order.entity import ServiceOrderStatusTransition
from src.infrastructure.budget_approval import SqlAlchemyApprovedBudgetServiceOrderCreator
from src.infrastructure.database import (
    BudgetModel,
    CustomerModel,
    ServiceOrderModel,
    VehicleModel,
)
from src.infrastructure.observability.json_logging import JsonLogFormatter
from src.infrastructure.persistence.service_order_repository import (
    SqlAlchemyServiceOrderRepository,
)
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


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


def _persist_order(db_session) -> ServiceOrderModel:
    customer = CustomerModel(
        name="Sensitive Customer Name",
        email="customer@example.com",
        phone="+55 11 99999-9999",
        address="Sensitive address",
    )
    db_session.add(customer)
    db_session.flush()
    vehicle = VehicleModel(
        customer_id=customer.id,
        plate="TLM5A01",
        state="SP",
        city="São Paulo",
        color="Preto",
        brand="Marca",
        model="Modelo",
        year=2026,
    )
    db_session.add(vehicle)
    db_session.flush()
    created_at = datetime(2026, 11, 1, 10, 0)
    order = ServiceOrderModel(
        customer_id=customer.id,
        vehicle_id=vehicle.id,
        status=ServiceOrderStatus.EM_DIAGNOSTICO,
        created_at=created_at,
    )
    db_session.add(order)
    db_session.commit()
    return order


def test_status_duration_is_emitted_only_after_commit_without_personal_data(db_session):
    model = _persist_order(db_session)
    repository = SqlAlchemyServiceOrderRepository(db_session)
    service_order = repository.get_by_id(model.id)
    assert service_order is not None
    occurred_at = datetime(
        2026,
        11,
        1,
        13,
        45,
        tzinfo=timezone(timedelta(hours=3)),
    )
    service_order.status = ServiceOrderStatus.AGUARDANDO_APROVACAO
    service_order.status_history.append(
        ServiceOrderStatusTransition(
            from_status=ServiceOrderStatus.EM_DIAGNOSTICO,
            to_status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
            transition_type="budget_submitted",
            occurred_at=occurred_at,
        )
    )
    logger, handler, payloads, previous_level, previous_disabled = _capture_business_logs()
    try:
        repository.save(service_order)
        assert payloads == []
        SqlAlchemyUnitOfWork(db_session).commit()
    finally:
        _restore_business_logs(logger, handler, previous_level, previous_disabled)

    assert len(payloads) == 1
    assert payloads[0]["duration_ms"] == int(timedelta(minutes=45).total_seconds() * 1000)
    assert "service_order_id" not in payloads[0]
    serialized = json.dumps(payloads, ensure_ascii=False)
    assert "Sensitive Customer Name" not in serialized
    assert "customer@example.com" not in serialized


def test_rollback_discards_pending_status_duration(db_session):
    model = _persist_order(db_session)
    repository = SqlAlchemyServiceOrderRepository(db_session)
    service_order = repository.get_by_id(model.id)
    assert service_order is not None
    service_order.status = ServiceOrderStatus.AGUARDANDO_APROVACAO
    service_order.status_history.append(
        ServiceOrderStatusTransition(
            from_status=ServiceOrderStatus.EM_DIAGNOSTICO,
            to_status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
            transition_type="budget_submitted",
        )
    )
    logger, handler, payloads, previous_level, previous_disabled = _capture_business_logs()
    try:
        repository.save(service_order)
        db_session.rollback()
        SqlAlchemyUnitOfWork(db_session).commit()
    finally:
        _restore_business_logs(logger, handler, previous_level, previous_disabled)

    assert payloads == []


def test_commit_failure_rolls_back_and_drops_pending_event(db_session, monkeypatch):
    from src.infrastructure.observability.business_telemetry import (
        ServiceOrderCreatedEvent,
        queue_business_event,
    )

    queue_business_event(
        db_session,
        ServiceOrderCreatedEvent(
            occurred_at=datetime.now(timezone.utc),
            status=ServiceOrderStatus.RECEBIDA,
        ),
    )
    logger, handler, payloads, previous_level, previous_disabled = _capture_business_logs()

    def _fail_commit():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", _fail_commit)
    try:
        with pytest.raises(RuntimeError, match="commit failed"):
            SqlAlchemyUnitOfWork(db_session).commit()
    finally:
        _restore_business_logs(logger, handler, previous_level, previous_disabled)

    assert payloads == []
    assert "service_order_business_telemetry" not in db_session.info


def test_created_volume_event_is_post_commit_and_idempotent(db_session):
    customer = CustomerModel(
        name="Customer",
        email="created@example.com",
        address="Address",
    )
    db_session.add(customer)
    db_session.flush()
    vehicle = VehicleModel(
        customer_id=customer.id,
        plate="CRT5A01",
        state="SP",
        city="São Paulo",
        color="Branco",
        brand="Marca",
        model="Modelo",
        year=2026,
    )
    db_session.add(vehicle)
    db_session.flush()
    budget_model = BudgetModel(customer_id=customer.id, vehicle_id=vehicle.id)
    db_session.add(budget_model)
    db_session.commit()
    budget = Budget(
        id=budget_model.id,
        customer_id=customer.id,
        vehicle_id=vehicle.id,
    )
    creator = SqlAlchemyApprovedBudgetServiceOrderCreator(db_session)
    logger, handler, payloads, previous_level, previous_disabled = _capture_business_logs()
    try:
        created = creator.create_from_budget(budget)
        assert payloads == []
        SqlAlchemyUnitOfWork(db_session).commit()
        duplicate = creator.create_from_budget(budget)
        SqlAlchemyUnitOfWork(db_session).commit()
    finally:
        _restore_business_logs(logger, handler, previous_level, previous_disabled)

    assert created.id == duplicate.id
    assert [payload["event"] for payload in payloads] == ["ServiceOrderCreated"]
    assert "service_order_id" not in payloads[0]
