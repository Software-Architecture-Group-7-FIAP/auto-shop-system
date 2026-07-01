from dataclasses import replace
from datetime import datetime

import pytest

from src.application.services.invoice_service import InvoiceService
from src.domain.billing.entity import Invoice
from src.domain.enums import InvoiceStatus, ServiceOrderStatus
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.service_order.entity import ServiceOrder, ServiceOrderServiceLine


class InMemoryInvoiceRepository:
    def __init__(self, invoices: list[Invoice] | None = None):
        self.invoices = {
            invoice.id: invoice for invoice in invoices or [] if invoice.id is not None
        }
        self.next_id = 1

    def add(self, invoice: Invoice) -> Invoice:
        created = replace(invoice, id=self.next_id)
        self.invoices[created.id] = created
        self.next_id += 1
        return created

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        return self.invoices.get(invoice_id)

    def get_by_service_order_id(self, service_order_id: int) -> Invoice | None:
        for invoice in self.invoices.values():
            if invoice.service_order_id == service_order_id:
                return invoice
        return None

    def save(self, invoice: Invoice) -> Invoice:
        assert invoice.id is not None
        self.invoices[invoice.id] = invoice
        return invoice


class InMemoryServiceOrderRepository:
    def __init__(self, service_orders: list[ServiceOrder] | None = None):
        self.service_orders = {
            service_order.id: service_order
            for service_order in service_orders or []
            if service_order.id is not None
        }

    def get_by_id(self, service_order_id: int) -> ServiceOrder | None:
        return self.service_orders.get(service_order_id)

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrder]:
        orders = list(self.service_orders.values())
        if status:
            return [order for order in orders if order.status == status]
        return orders

    def list_with_execution_times(self) -> list[ServiceOrder]:
        return []

    def list_by_ids_and_status(
        self,
        service_order_ids: list[int],
        status: ServiceOrderStatus,
    ) -> list[ServiceOrder]:
        return [
            service_order
            for service_order in self.service_orders.values()
            if service_order.id in service_order_ids and service_order.status == status
        ]

    def save(self, service_order: ServiceOrder) -> ServiceOrder:
        assert service_order.id is not None
        self.service_orders[service_order.id] = service_order
        return service_order


class FakeClock:
    def __init__(self, value: datetime):
        self.value = value

    def now(self) -> datetime:
        return self.value


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def make_service_order(**overrides) -> ServiceOrder:
    base = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.FINALIZADA,
        total_price=150.0,
        service_lines=[
            ServiceOrderServiceLine(
                id=1,
                service_order_id=1,
                service_id=10,
                quantity=1,
                unit_price=150.0,
            )
        ],
    )
    return replace(base, **overrides)


def make_service(
    invoices: InMemoryInvoiceRepository | None = None,
    service_orders: InMemoryServiceOrderRepository | None = None,
    uow: FakeUnitOfWork | None = None,
) -> InvoiceService:
    return InvoiceService(
        invoices=invoices or InMemoryInvoiceRepository(),
        service_orders=service_orders
        or InMemoryServiceOrderRepository([make_service_order()]),
        clock=FakeClock(datetime(2026, 1, 1, 10, 0, 0)),
        uow=uow or FakeUnitOfWork(),
    )


def test_invoice_service_creates_invoice_without_sqlalchemy():
    invoices = InMemoryInvoiceRepository()
    uow = FakeUnitOfWork()
    service = make_service(invoices=invoices, uow=uow)

    invoice = service.create_invoice(1)

    assert invoice.id == 1
    assert invoice.service_order_id == 1
    assert invoice.amount == 150.0
    assert invoice.status == InvoiceStatus.PENDING
    assert invoices.get_by_id(1) == invoice
    assert uow.commits == 1


def test_invoice_service_rejects_missing_service_order():
    service = make_service(service_orders=InMemoryServiceOrderRepository())

    with pytest.raises(NotFoundError, match="OS não encontrada"):
        service.create_invoice(1)


def test_invoice_service_rejects_non_finalized_service_order():
    service = make_service(
        service_orders=InMemoryServiceOrderRepository(
            [make_service_order(status=ServiceOrderStatus.EM_EXECUCAO)]
        )
    )

    with pytest.raises(
        ValidationError,
        match="OS deve estar finalizada para gerar fatura",
    ):
        service.create_invoice(1)


def test_invoice_service_rejects_duplicate_invoice():
    service = make_service(
        invoices=InMemoryInvoiceRepository(
            [Invoice(id=1, service_order_id=1, amount=150.0)]
        )
    )

    with pytest.raises(ValidationError, match="Fatura já existe para esta OS"):
        service.create_invoice(1)


def test_invoice_service_pays_invoice_and_delivers_service_order():
    invoice = Invoice(id=1, service_order_id=1, amount=150.0)
    invoices = InMemoryInvoiceRepository([invoice])
    service_orders = InMemoryServiceOrderRepository([make_service_order()])
    uow = FakeUnitOfWork()
    service = make_service(
        invoices=invoices,
        service_orders=service_orders,
        uow=uow,
    )

    paid = service.pay_invoice(1)

    assert paid.status == InvoiceStatus.PAID
    assert paid.paid_at == datetime(2026, 1, 1, 10, 0, 0)
    assert service_orders.get_by_id(1).status == ServiceOrderStatus.ENTREGUE
    assert uow.commits == 1


def test_invoice_service_gets_invoice_by_service_order():
    invoice = Invoice(id=1, service_order_id=1, amount=150.0)
    service = make_service(invoices=InMemoryInvoiceRepository([invoice]))

    assert service.get_by_service_order_id(1) == invoice


def test_invoice_service_rejects_missing_service_order_invoice():
    service = make_service()

    with pytest.raises(NotFoundError, match="Fatura não encontrada"):
        service.get_by_service_order_id(1)


def test_invoice_service_rejects_missing_invoice():
    service = make_service()

    with pytest.raises(NotFoundError, match="Fatura não encontrada"):
        service.pay_invoice(1)


def test_invoice_service_delivers_service_order():
    invoice = Invoice(id=1, service_order_id=1, amount=150.0)
    invoice.pay(datetime(2026, 1, 1, 10, 0, 0))
    service_orders = InMemoryServiceOrderRepository([make_service_order()])
    uow = FakeUnitOfWork()
    service = make_service(
        invoices=InMemoryInvoiceRepository([invoice]),
        service_orders=service_orders,
        uow=uow,
    )

    delivered = service.deliver(1)

    assert delivered.status == ServiceOrderStatus.ENTREGUE
    assert service_orders.get_by_id(1).status == ServiceOrderStatus.ENTREGUE
    assert uow.commits == 1


def test_invoice_service_rejects_deliver_before_finalized():
    service = make_service(
        service_orders=InMemoryServiceOrderRepository(
            [make_service_order(status=ServiceOrderStatus.EM_EXECUCAO)]
        )
    )

    with pytest.raises(ValidationError, match="OS deve estar finalizada para ser entregue"):
        service.deliver(1)


def test_invoice_service_rejects_deliver_without_paid_invoice():
    service = make_service()

    with pytest.raises(ValidationError, match="Fatura deve estar paga para entregar a OS"):
        service.deliver(1)


def test_invoice_service_calculates_amount_from_lines():
    service_order = make_service_order(
        total_price=80.0,
        service_lines=[
            ServiceOrderServiceLine(
                id=1,
                service_order_id=1,
                service_id=10,
                quantity=2,
                unit_price=40.0,
            )
        ],
        product_lines=[],
    )
    service = make_service(
        service_orders=InMemoryServiceOrderRepository([service_order])
    )

    invoice = service.create_invoice(1)

    assert invoice.amount == 80.0


def test_invoice_service_rejects_total_that_diverges_from_lines():
    service_order = make_service_order(
        total_price=999.0,
        service_lines=[
            ServiceOrderServiceLine(
                id=1,
                service_order_id=1,
                service_id=10,
                quantity=2,
                unit_price=40.0,
            )
        ],
        product_lines=[],
    )
    service = make_service(
        service_orders=InMemoryServiceOrderRepository([service_order])
    )

    with pytest.raises(ValidationError, match="Total da OS diverge"):
        service.create_invoice(1)


def test_invoice_service_rejects_unpriced_lines():
    service_order = make_service_order(
        service_lines=[
            ServiceOrderServiceLine(
                id=1,
                service_order_id=1,
                service_id=10,
                quantity=1,
                unit_price=0.0,
            )
        ],
    )
    service = make_service(
        service_orders=InMemoryServiceOrderRepository([service_order])
    )

    with pytest.raises(ValidationError, match="precificação válida"):
        service.create_invoice(1)


def test_invoice_service_rejects_duplicate_payment():
    invoice = Invoice(id=1, service_order_id=1, amount=150.0)
    invoice.pay(datetime(2026, 1, 1, 10, 0, 0))
    service = make_service(invoices=InMemoryInvoiceRepository([invoice]))

    with pytest.raises(ValidationError, match="Fatura já está paga"):
        service.pay_invoice(1)
