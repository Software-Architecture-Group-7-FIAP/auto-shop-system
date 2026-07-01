from datetime import datetime

import pytest

from src.domain.billing.entity import Invoice
from src.domain.enums import InvoiceStatus, ServiceOrderStatus
from src.domain.exceptions import ValidationError
from src.domain.service_order.entity import ServiceOrder


def test_invoice_create_defaults_to_pending_status():
    invoice = Invoice.create(service_order_id=1, amount=150.0)

    assert invoice.service_order_id == 1
    assert invoice.amount == 150.0
    assert invoice.status == InvoiceStatus.PENDING
    assert invoice.paid_at is None


def test_invoice_pay_sets_status_and_paid_at():
    paid_at = datetime(2026, 1, 1, 10, 0, 0)
    invoice = Invoice.create(service_order_id=1, amount=150.0)

    invoice.pay(paid_at)

    assert invoice.status == InvoiceStatus.PAID
    assert invoice.paid_at == paid_at


def test_invoice_pay_rejects_already_paid():
    paid_at = datetime(2026, 1, 1, 10, 0, 0)
    invoice = Invoice.create(service_order_id=1, amount=150.0)
    invoice.pay(paid_at)

    with pytest.raises(ValidationError, match="Fatura já está paga"):
        invoice.pay(paid_at)


def test_mark_delivered_requires_finalized_status():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.EM_EXECUCAO,
    )

    with pytest.raises(ValidationError, match="OS deve estar finalizada para ser entregue"):
        service_order.mark_delivered()


def test_mark_delivered_sets_entregue_from_finalizada():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.FINALIZADA,
    )

    service_order.mark_delivered()

    assert service_order.status == ServiceOrderStatus.ENTREGUE
