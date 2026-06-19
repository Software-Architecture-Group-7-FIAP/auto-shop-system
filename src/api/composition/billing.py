from sqlalchemy.orm import Session

from src.application.services.invoice_service import InvoiceService
from src.infrastructure.billing import SystemBillingClock
from src.infrastructure.persistence.billing_repository import SqlAlchemyInvoiceRepository
from src.infrastructure.persistence.service_order_repository import (
    SqlAlchemyServiceOrderRepository,
)
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_invoice_service(db: Session) -> InvoiceService:
    return InvoiceService(
        invoices=SqlAlchemyInvoiceRepository(db),
        service_orders=SqlAlchemyServiceOrderRepository(db),
        clock=SystemBillingClock(),
        uow=SqlAlchemyUnitOfWork(db),
    )
