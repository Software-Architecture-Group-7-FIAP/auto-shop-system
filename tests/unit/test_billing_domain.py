from datetime import datetime

from src.domain.billing.entity import Invoice
from src.domain.enums import InvoiceStatus


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
