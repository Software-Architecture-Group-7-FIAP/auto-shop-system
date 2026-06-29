from datetime import datetime

import pytest

from src.domain.enums import ServiceOrderStatus, StockWithdrawalStatus
from src.domain.exceptions import ValidationError
from src.domain.execution.entity import (
    StockWithdrawal,
    enqueue_service_order,
    finish_service_order,
    start_service_order,
)
from src.domain.service_order.entity import ServiceOrder


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
        finish_service_order(service_order, datetime(2026, 1, 1, 10, 0, 0))
