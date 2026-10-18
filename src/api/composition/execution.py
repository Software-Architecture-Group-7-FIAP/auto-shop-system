from sqlalchemy.orm import Session

from src.application.services.execution_service import ExecutionService
from src.infrastructure.execution import (
    SettingsExecutionNotificationRecipient,
    SmtpExecutionEmailSender,
    SystemExecutionClock,
)
from src.infrastructure.events.eventbridge import EventBridgeServiceOrderEventPublisher
from src.infrastructure.persistence.execution_repository import (
    SqlAlchemyExecutionProductGateway,
    SqlAlchemyExecutionReservationGateway,
    SqlAlchemyStockWithdrawalRepository,
)
from src.infrastructure.persistence.service_order_repository import (
    SqlAlchemyServiceOrderRepository,
)
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.config import settings


def compose_execution_service(db: Session) -> ExecutionService:
    return ExecutionService(
        service_orders=SqlAlchemyServiceOrderRepository(db),
        withdrawals=SqlAlchemyStockWithdrawalRepository(db),
        products=SqlAlchemyExecutionProductGateway(db),
        reservations=SqlAlchemyExecutionReservationGateway(db),
        clock=SystemExecutionClock(),
        recipients=SettingsExecutionNotificationRecipient(),
        emails=SmtpExecutionEmailSender(),
        uow=SqlAlchemyUnitOfWork(db),
        event_publisher=EventBridgeServiceOrderEventPublisher(
            settings.service_order_event_bus_name
        ),
    )
