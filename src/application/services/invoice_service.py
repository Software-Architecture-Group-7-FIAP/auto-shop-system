from src.application.ports.billing import BillingClock
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.billing.entity import Invoice
from src.domain.billing.rules import (
    calculate_invoice_amount,
    validate_invoice_total_matches_lines,
    validate_priced_lines,
)
from src.domain.billing.repository import InvoiceRepository
from src.domain.enums import InvoiceStatus, ServiceOrderStatus
from src.domain.exceptions import NotFoundError, ValidationError
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

    def pay_invoice(self, invoice_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> Invoice:
        invoice = self.get_by_id(invoice_id)
        invoice.pay(self.clock.now())
        updated = self.invoices.save(invoice)

        service_order = self.service_orders.get_by_id(invoice.service_order_id)
        if service_order:
            service_order.mark_delivered(actor_id=actor_id, request_id=request_id)
            self.service_orders.save(service_order)

        self.uow.commit()
        return updated

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
