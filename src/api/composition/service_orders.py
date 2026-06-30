from sqlalchemy.orm import Session

from src.config import settings
from src.application.services.service_order_email_service import ServiceOrderEmailService
from src.application.services.service_order_service import ServiceOrderService
from src.infrastructure.auth.service_order_tracking import HmacServiceOrderTrackingTokenService
from src.infrastructure.persistence.service_order_repository import (
    SqlAlchemyServiceOrderContactLookup,
    SqlAlchemyServiceOrderRepository,
)
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.infrastructure.service_order import (
    ReportLabServiceOrderPdfGenerator,
    SmtpServiceOrderEmailSender,
)


def compose_service_order_service(db: Session) -> ServiceOrderService:
    return ServiceOrderService(
        service_orders=SqlAlchemyServiceOrderRepository(db),
        contacts=SqlAlchemyServiceOrderContactLookup(db),
        tracking_tokens=HmacServiceOrderTrackingTokenService(),
        uow=SqlAlchemyUnitOfWork(db),
    )


def compose_service_order_email_service(db: Session) -> ServiceOrderEmailService:
    return ServiceOrderEmailService(
        service_orders=SqlAlchemyServiceOrderRepository(db),
        contacts=SqlAlchemyServiceOrderContactLookup(db),
        pdfs=ReportLabServiceOrderPdfGenerator(),
        emails=SmtpServiceOrderEmailSender(),
        tracking_tokens=HmacServiceOrderTrackingTokenService(),
        frontend_public_url=settings.frontend_public_url,
        uow=SqlAlchemyUnitOfWork(db),
    )
