from dataclasses import dataclass
from datetime import datetime

from src.domain.enums import InvoiceStatus


@dataclass
class Invoice:
    id: int | None
    service_order_id: int
    amount: float
    status: InvoiceStatus = InvoiceStatus.PENDING
    paid_at: datetime | None = None
    created_at: datetime | None = None

    @classmethod
    def create(cls, service_order_id: int, amount: float) -> "Invoice":
        return cls(
            id=None,
            service_order_id=service_order_id,
            amount=amount,
        )

    def pay(self, paid_at: datetime) -> None:
        self.status = InvoiceStatus.PAID
        self.paid_at = paid_at
