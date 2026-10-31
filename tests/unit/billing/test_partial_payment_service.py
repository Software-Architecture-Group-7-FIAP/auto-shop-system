from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from src.application.services.invoice_service import InvoiceService
from src.domain.billing.entity import Invoice
from src.domain.enums import InvoiceStatus, PaymentMethod, ServiceOrderStatus
from src.domain.exceptions import ConflictError, ValidationError
from src.domain.service_order.entity import ServiceOrder


class InMemoryPaymentInvoiceRepository:
    def __init__(self, invoice: Invoice):
        self.invoice = invoice
        self.added_payments = []

    def add(self, invoice):
        return invoice

    def get_by_id(self, invoice_id):
        return self.invoice if invoice_id == self.invoice.id else None

    def get_by_id_for_update(self, invoice_id):
        return self.get_by_id(invoice_id)

    def get_by_service_order_id(self, service_order_id):
        return self.invoice if service_order_id == self.invoice.service_order_id else None

    def get_payment_by_idempotency_key(self, invoice_id, idempotency_key):
        return next(
            (
                payment
                for payment in self.invoice.payments
                if payment.invoice_id == invoice_id
                and payment.idempotency_key == idempotency_key
            ),
            None,
        )

    def add_payment(self, payment):
        self.added_payments.append(payment)
        return payment

    def save(self, invoice):
        self.invoice = invoice
        return invoice


class InMemoryServiceOrderRepository:
    def __init__(self, service_order):
        self.service_order = service_order

    def get_by_id(self, service_order_id):
        return self.service_order if service_order_id == self.service_order.id else None

    def save(self, service_order):
        self.service_order = service_order
        return service_order


class FixedClock:
    def now(self):
        return datetime(2026, 8, 31, 12, 0, 0)


class UnitOfWork:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def make_service_order(status=ServiceOrderStatus.FINALIZADA):
    return ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=status,
        total_price=100.0,
    )


def make_service(status=ServiceOrderStatus.FINALIZADA):
    invoice = Invoice(id=1, service_order_id=1, amount=Decimal("100.00"))
    service_orders = InMemoryServiceOrderRepository(make_service_order(status))
    unit_of_work = UnitOfWork()
    return (
        InvoiceService(
            invoices=InMemoryPaymentInvoiceRepository(invoice),
            service_orders=service_orders,
            clock=FixedClock(),
            uow=unit_of_work,
        ),
        invoice,
        service_orders,
        unit_of_work,
    )


def test_service_records_partial_payment_without_delivering_order():
    service, invoice, service_orders, unit_of_work = make_service()

    result = service.record_payment(
        1,
        amount=Decimal("40.00"),
        method=PaymentMethod.PIX,
        actor_id=9,
        idempotency_key="request-1",
    )

    assert result.status == InvoiceStatus.PARTIALLY_PAID
    assert result.balance == Decimal("60.00")
    assert service_orders.service_order.status == ServiceOrderStatus.FINALIZADA
    assert result.payments[0].user_id == 9
    assert unit_of_work.commits == 1


def test_service_replays_same_idempotency_key_without_creating_payment_twice():
    service, invoice, _, _ = make_service()
    kwargs = {
        "amount": Decimal("40.00"),
        "method": PaymentMethod.PIX,
        "actor_id": 9,
        "idempotency_key": "request-1",
    }

    first = service.record_payment(1, **kwargs)
    second = service.record_payment(1, **kwargs)

    assert first.status == InvoiceStatus.PARTIALLY_PAID
    assert second.status == InvoiceStatus.PARTIALLY_PAID
    assert len(invoice.payments) == 1


def test_service_rejects_reusing_idempotency_key_with_different_payment():
    service, _, _, _ = make_service()
    service.record_payment(
        1,
        amount=Decimal("40.00"),
        method=PaymentMethod.PIX,
        actor_id=9,
        idempotency_key="request-1",
    )

    with pytest.raises(ConflictError, match="idempotência"):
        service.record_payment(
            1,
            amount=Decimal("50.00"),
            method=PaymentMethod.CARTAO,
            actor_id=9,
            idempotency_key="request-1",
        )


def test_service_delivers_only_after_exact_payment_on_finalized_order():
    service, _, service_orders, _ = make_service()

    result = service.record_payment(
        1,
        amount=Decimal("100.00"),
        method=PaymentMethod.TRANSFERENCIA,
        actor_id=9,
        idempotency_key="request-1",
    )

    assert result.status == InvoiceStatus.PAID
    assert service_orders.service_order.status == ServiceOrderStatus.ENTREGUE


def test_service_does_not_deliver_when_order_is_not_finalized():
    service, _, service_orders, _ = make_service(ServiceOrderStatus.EM_EXECUCAO)

    result = service.record_payment(
        1,
        amount=Decimal("100.00"),
        method=PaymentMethod.DINHEIRO,
        actor_id=9,
        idempotency_key="request-1",
    )

    assert result.status == InvoiceStatus.PAID
    assert service_orders.service_order.status == ServiceOrderStatus.EM_EXECUCAO
