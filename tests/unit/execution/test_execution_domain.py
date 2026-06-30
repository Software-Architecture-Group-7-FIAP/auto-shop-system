from datetime import datetime

import pytest

from src.domain.enums import Priority, ServiceOrderStatus, StockWithdrawalStatus
from src.domain.exceptions import ValidationError
from src.domain.execution.entity import (
    StockWithdrawal,
    enqueue_service_order,
    finish_service_order,
    order_execution_queue,
    start_service_order,
)
from src.domain.service_order.entity import ServiceOrder, ServiceOrderProductLine


def test_stock_withdrawal_create_defaults_to_pending_status():
    withdrawal = StockWithdrawal.create(
        service_order_id=1,
        product_id=2,
        quantity=3,
    )

    assert withdrawal.service_order_id == 1
    assert withdrawal.product_id == 2
    assert withdrawal.quantity == 3
    assert withdrawal.status == StockWithdrawalStatus.PENDING


def test_stock_withdrawal_rejects_non_positive_quantity():
    with pytest.raises(ValidationError, match="Quantidade deve ser maior que zero"):
        StockWithdrawal.create(service_order_id=1, product_id=2, quantity=0)


def test_stock_withdrawal_fulfill_sets_status_and_timestamp():
    withdrawal = StockWithdrawal.create(service_order_id=1, product_id=2, quantity=3)
    fulfilled_at = datetime(2026, 1, 1, 9, 0, 0)

    withdrawal.fulfill(fulfilled_at)

    assert withdrawal.status == StockWithdrawalStatus.FULFILLED
    assert withdrawal.fulfilled_at == fulfilled_at


def test_stock_withdrawal_fulfill_rejects_non_pending_status():
    withdrawal = StockWithdrawal.create(service_order_id=1, product_id=2, quantity=3)
    withdrawal.fulfill(datetime(2026, 1, 1, 9, 0, 0))

    with pytest.raises(
        ValidationError,
        match="Solicitação de retirada já foi atendida ou cancelada",
    ):
        withdrawal.fulfill(datetime(2026, 1, 1, 10, 0, 0))


def test_order_execution_queue_sorts_by_priority_then_created_at():
    low = ServiceOrder(
        id=1,
        budget_id=None,
        customer_id=1,
        vehicle_id=1,
        priority=Priority.LOW,
        created_at=datetime(2026, 1, 1),
    )
    urgent_later = ServiceOrder(
        id=2,
        budget_id=None,
        customer_id=1,
        vehicle_id=1,
        priority=Priority.URGENT,
        created_at=datetime(2026, 1, 2),
    )
    urgent_earlier = ServiceOrder(
        id=3,
        budget_id=None,
        customer_id=1,
        vehicle_id=1,
        priority=Priority.URGENT,
        created_at=datetime(2026, 1, 1),
    )
    normal = ServiceOrder(
        id=4,
        budget_id=None,
        customer_id=1,
        vehicle_id=1,
        priority=Priority.NORMAL,
        created_at=datetime(2026, 1, 1),
    )

    ordered = order_execution_queue([low, urgent_later, urgent_earlier, normal])

    assert [so.id for so in ordered] == [3, 2, 4, 1]


def test_enqueue_service_order_requires_waiting_approval_status():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.RECEBIDA,
    )

    with pytest.raises(
        ValidationError,
        match="OS deve estar aguardando aprovação para entrar na fila",
    ):
        enqueue_service_order(service_order)


def test_start_service_order_sets_status_and_started_at():
    started_at = datetime(2026, 1, 1, 8, 0, 0)
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.EM_DIAGNOSTICO,
        mechanic_name="João",
    )

    start_service_order(service_order, started_at)

    assert service_order.status == ServiceOrderStatus.EM_EXECUCAO
    assert service_order.started_at == started_at


def test_finish_service_order_requires_in_progress_status():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.EM_DIAGNOSTICO,
    )

    with pytest.raises(
        ValidationError,
        match="OS deve estar em execução para ser finalizada",
    ):
        finish_service_order(service_order, datetime(2026, 1, 1, 10, 0, 0), {})


def test_finish_service_order_blocks_when_withdrawal_pending():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.EM_EXECUCAO,
        product_lines=[
            ServiceOrderProductLine(
                id=1, service_order_id=1, product_id=10, quantity=2, unit_price=5.0
            )
        ],
    )

    with pytest.raises(
        ValidationError,
        match="itens reservados sem retirada de estoque confirmada",
    ):
        finish_service_order(service_order, datetime(2026, 1, 1, 10, 0, 0), {10: 1})


def test_finish_service_order_succeeds_when_withdrawals_cover_quantities():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.EM_EXECUCAO,
        product_lines=[
            ServiceOrderProductLine(
                id=1, service_order_id=1, product_id=10, quantity=2, unit_price=5.0
            )
        ],
    )
    finished_at = datetime(2026, 1, 1, 10, 0, 0)

    finish_service_order(service_order, finished_at, {10: 2})

    assert service_order.status == ServiceOrderStatus.FINALIZADA
    assert service_order.finished_at == finished_at
