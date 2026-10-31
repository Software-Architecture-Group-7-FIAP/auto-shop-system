from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from src.domain.enums import InvoiceStatus, PaymentMethod
from src.domain.exceptions import ValidationError


CENT = Decimal("0.01")


def to_money(value: Decimal | int | float | str) -> Decimal:
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Valor monetário inválido") from exc
    if not amount.is_finite() or amount != amount.quantize(CENT):
        raise ValidationError("Valor monetário deve ter no máximo duas casas decimais")
    return amount.quantize(CENT)


@dataclass(frozen=True)
class Payment:
    id: int | None
    invoice_id: int
    amount: Decimal
    method: PaymentMethod
    paid_at: datetime
    user_id: int
    idempotency_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", to_money(self.amount))


@dataclass
class Invoice:
    id: int | None
    service_order_id: int
    amount: Decimal
    status: InvoiceStatus = InvoiceStatus.PENDING
    paid_at: datetime | None = None
    created_at: datetime | None = None
    payments: list[Payment] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.amount = to_money(self.amount)

    @classmethod
    def create(
        cls, service_order_id: int, amount: Decimal | int | float | str
    ) -> "Invoice":
        return cls(
            id=None,
            service_order_id=service_order_id,
            amount=to_money(amount),
        )

    @property
    def total_paid(self) -> Decimal:
        if self.status == InvoiceStatus.PAID and not self.payments:
            return self.amount
        return sum((payment.amount for payment in self.payments), Decimal("0.00"))

    @property
    def balance(self) -> Decimal:
        return max(Decimal("0.00"), self.amount - self.total_paid)

    def record_payment(
        self,
        *,
        amount: Decimal | int | float | str,
        method: PaymentMethod | str,
        paid_at: datetime,
        user_id: int,
        idempotency_key: str,
    ) -> Payment:
        if self.status == InvoiceStatus.PAID:
            raise ValidationError("Fatura já está paga")
        payment_amount = to_money(amount)
        if payment_amount <= Decimal("0.00"):
            raise ValidationError("O valor do pagamento deve ser maior que zero")
        try:
            payment_method = PaymentMethod(method)
        except ValueError as exc:
            raise ValidationError("método de pagamento inválido") from exc
        if not idempotency_key.strip():
            raise ValidationError("A chave de idempotência é obrigatória")
        if payment_amount > self.balance:
            raise ValidationError("O pagamento excede o saldo da fatura")

        payment = Payment(
            id=None,
            invoice_id=self.id or 0,
            amount=payment_amount,
            method=payment_method,
            paid_at=paid_at,
            user_id=user_id,
            idempotency_key=idempotency_key.strip(),
        )
        self.payments.append(payment)
        self.status = (
            InvoiceStatus.PAID
            if self.balance == Decimal("0.00")
            else InvoiceStatus.PARTIALLY_PAID
        )
        self.paid_at = paid_at if self.status == InvoiceStatus.PAID else None
        return payment

    def pay(self, paid_at: datetime) -> None:
        """Compatibility helper for the former one-shot payment API."""
        self.record_payment(
            amount=self.balance,
            method=PaymentMethod.DINHEIRO,
            paid_at=paid_at,
            user_id=0,
            idempotency_key=f"legacy-{paid_at.isoformat()}",
        )
