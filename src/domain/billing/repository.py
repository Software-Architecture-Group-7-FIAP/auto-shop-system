from typing import Protocol

from src.domain.billing.entity import Invoice, Payment


class InvoiceRepository(Protocol):
    def add(self, invoice: Invoice) -> Invoice:
        ...

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        ...

    def get_by_id_for_update(self, invoice_id: int) -> Invoice | None:
        ...

    def get_by_service_order_id(self, service_order_id: int) -> Invoice | None:
        ...

    def save(self, invoice: Invoice) -> Invoice:
        ...

    def get_payment_by_idempotency_key(
        self, invoice_id: int, idempotency_key: str
    ) -> Payment | None:
        ...

    def add_payment(self, payment: Payment) -> Payment:
        ...
