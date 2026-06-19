from sqlalchemy.orm import Session

from src.application.services.customer_service import CustomerService
from src.infrastructure.persistence.customer_repository import SqlAlchemyCustomerRepository
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_customer_service(db: Session) -> CustomerService:
    return CustomerService(
        customers=SqlAlchemyCustomerRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
