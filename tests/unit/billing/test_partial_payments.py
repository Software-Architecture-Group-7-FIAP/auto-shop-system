from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.billing.entity import Invoice
from src.domain.enums import InvoiceStatus, PaymentMethod
from src.domain.exceptions import ValidationError


PAID_AT = datetime(2026, 8, 31, 12, 0, 0)


def test_invoice_accepts_multiple_partial_payments_using_decimal_balance():
    invoice = Invoice.create(service_order_id=10, amount=Decimal("100.00"))

    first = invoice.record_payment(
        amount=Decimal("35.10"),
        method=PaymentMethod.PIX,
        paid_at=PAID_AT,
        user_id=7,
        idempotency_key="payment-1",
    )
    second = invoice.record_payment(
        amount=Decimal("64.90"),
        method=PaymentMethod.CARTAO,
        paid_at=PAID_AT,
        user_id=8,
        idempotency_key="payment-2",
    )

    assert first.amount == Decimal("35.10")
    assert second.method == PaymentMethod.CARTAO
    assert invoice.total_paid == Decimal("100.00")
    assert invoice.balance == Decimal("0.00")
    assert invoice.status == InvoiceStatus.PAID
    assert invoice.paid_at == PAID_AT
    assert [payment.user_id for payment in invoice.payments] == [7, 8]


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-0.01")])
def test_invoice_rejects_non_positive_payment(amount):
    invoice = Invoice.create(service_order_id=10, amount=Decimal("100.00"))

    with pytest.raises(ValidationError, match="maior que zero"):
        invoice.record_payment(
            amount=amount,
            method=PaymentMethod.DINHEIRO,
            paid_at=PAID_AT,
            user_id=7,
            idempotency_key="payment-1",
        )


def test_invoice_rejects_payment_above_balance_without_float_rounding():
    invoice = Invoice.create(service_order_id=10, amount=Decimal("0.30"))
    invoice.record_payment(
        amount=Decimal("0.10"),
        method=PaymentMethod.TRANSFERENCIA,
        paid_at=PAID_AT,
        user_id=7,
        idempotency_key="payment-1",
    )

    with pytest.raises(ValidationError, match="excede o saldo"):
        invoice.record_payment(
            amount=Decimal("0.21"),
            method=PaymentMethod.TRANSFERENCIA,
            paid_at=PAID_AT,
            user_id=7,
            idempotency_key="payment-2",
        )


def test_invoice_rejects_new_payment_after_paid():
    invoice = Invoice.create(service_order_id=10, amount=Decimal("10.00"))
    invoice.record_payment(
        amount=Decimal("10.00"),
        method=PaymentMethod.DINHEIRO,
        paid_at=PAID_AT,
        user_id=7,
        idempotency_key="payment-1",
    )

    with pytest.raises(ValidationError, match="já está paga"):
        invoice.record_payment(
            amount=Decimal("1.00"),
            method=PaymentMethod.PIX,
            paid_at=PAID_AT,
            user_id=7,
            idempotency_key="payment-2",
        )


def test_invoice_requires_supported_payment_method_and_idempotency_key():
    invoice = Invoice.create(service_order_id=10, amount=Decimal("10.00"))

    with pytest.raises(ValidationError, match="método de pagamento"):
        invoice.record_payment(
            amount=Decimal("1.00"),
            method="CHEQUE",
            paid_at=PAID_AT,
            user_id=7,
            idempotency_key="payment-1",
        )

    with pytest.raises(ValidationError, match="idempotência"):
        invoice.record_payment(
            amount=Decimal("1.00"),
            method=PaymentMethod.PIX,
            paid_at=PAID_AT,
            user_id=7,
            idempotency_key="",
        )
