from decimal import Decimal

from src.application.ports.billing import BillingClock
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.billing.entity import Invoice, Payment
from src.domain.billing.rules import (
    calculate_invoice_amount,
    validate_invoice_total_matches_lines,
    validate_priced_lines,
)
from src.domain.billing.repository import InvoiceRepository
from src.domain.enums import InvoiceStatus, PaymentMethod, ServiceOrderStatus
from src.domain.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from src.domain.service_order.entity import ServiceOrder
from src.domain.service_order.repository import ServiceOrderRepository


class InvoiceService:
    def __init__(
        self,
        invoices: InvoiceRepository,
        service_orders: ServiceOrderRepository,
        clock: BillingClock,
        uow: UnitOfWork,
    ):
        self.invoices = invoices
        self.service_orders = service_orders
        self.clock = clock
        self.uow = uow

    def create_invoice(self, service_order_id: int) -> Invoice:
        service_order = self.service_orders.get_by_id(service_order_id)
        if not service_order:
            raise NotFoundError("OS não encontrada")
        if service_order.status != ServiceOrderStatus.FINALIZADA:
            raise ValidationError("OS deve estar finalizada para gerar fatura")
        if self.invoices.get_by_service_order_id(service_order_id):
            raise ValidationError("Fatura já existe para esta OS")

        validate_priced_lines(service_order)
        validate_invoice_total_matches_lines(service_order)
        amount = calculate_invoice_amount(service_order)
        invoice = self.invoices.add(Invoice.create(service_order_id, amount))
        self.uow.commit()
        return invoice

    def record_payment(
        self,
        invoice_id: int,
        *,
        amount: Decimal,
        method: PaymentMethod,
        actor_id: int | None,
        idempotency_key: str,
        request_id: str | None = None,
    ) -> Invoice:
        if actor_id is None:
            raise UnauthorizedError("Usuário autenticado é obrigatório para registrar pagamento")
        invoice = self._get_for_update(invoice_id)
        existing = self._get_payment_by_key(invoice, idempotency_key)
        if existing:
            if existing.amount != amount or existing.method != method:
                raise ConflictError("Chave de idempotência já utilizada para outro pagamento")
            return invoice

        payment = invoice.record_payment(
            amount=amount,
            method=method,
            paid_at=self.clock.now(),
            user_id=actor_id,
            idempotency_key=idempotency_key,
        )
        try:
            self.invoices.add_payment(payment)
            updated = self.invoices.save(invoice)
            self._deliver_if_paid(updated, actor_id=actor_id, request_id=request_id)
            self.uow.commit()
            return updated
        except ConflictError:
            replay = self._get_payment_by_key(self._get_for_update(invoice_id), idempotency_key)
            if replay and replay.amount == amount and replay.method == method:
                return self._get_for_update(invoice_id)
            raise

    def pay_invoice(
        self,
        invoice_id: int,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> Invoice:
        """Compatibility path for clients of the former full-payment endpoint."""
        invoice = self._get_for_update(invoice_id)
        return self.record_payment(
            invoice_id,
            amount=invoice.balance,
            method=PaymentMethod.DINHEIRO,
            actor_id=actor_id or 0,
            idempotency_key=request_id or f"legacy-pay-{invoice_id}",
            request_id=request_id,
        )

    def get_by_service_order_id(self, service_order_id: int) -> Invoice:
        invoice = self.invoices.get_by_service_order_id(service_order_id)
        if not invoice:
            raise NotFoundError("Fatura não encontrada")
        return invoice

    def deliver(self, service_order_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> ServiceOrder:
        service_order = self.service_orders.get_by_id(service_order_id)
        if not service_order:
            raise NotFoundError("OS não encontrada")
        if service_order.status != ServiceOrderStatus.FINALIZADA:
            raise ValidationError("OS deve estar finalizada para ser entregue")
        invoice = self.invoices.get_by_service_order_id(service_order_id)
        if not invoice or invoice.status != InvoiceStatus.PAID:
            raise ValidationError("Fatura deve estar paga para entregar a OS")
        service_order.mark_delivered(actor_id=actor_id, request_id=request_id)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def get_by_id(self, invoice_id: int) -> Invoice:
        invoice = self.invoices.get_by_id(invoice_id)
        if not invoice:
            raise NotFoundError("Fatura não encontrada")
        return invoice

    def _get_for_update(self, invoice_id: int) -> Invoice:
        invoice = self.invoices.get_by_id_for_update(invoice_id)
        if not invoice:
            raise NotFoundError("Fatura não encontrada")
        return invoice

    def _get_payment_by_key(self, invoice: Invoice, idempotency_key: str) -> Payment | None:
        if invoice.id is None:
            return None
        return self.invoices.get_payment_by_idempotency_key(
            invoice.id,
            idempotency_key,
        )

    def _deliver_if_paid(
        self,
        invoice: Invoice,
        *,
        actor_id: int,
        request_id: str | None,
    ) -> None:
        if invoice.status != InvoiceStatus.PAID:
            return
        service_order = self.service_orders.get_by_id(invoice.service_order_id)
        if service_order and service_order.status == ServiceOrderStatus.FINALIZADA:
            service_order.mark_delivered(actor_id=actor_id, request_id=request_id)
            self.service_orders.save(service_order)
