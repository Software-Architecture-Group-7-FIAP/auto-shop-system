from sqlalchemy.orm import Session

from src.application.services.customer_public_lookup_service import CustomerPublicLookupService
from src.application.services.customer_service import CustomerService
from src.config import settings
from src.infrastructure.external.brasil_api_cnpj import HttpBrasilApiCnpjValidator
from src.infrastructure.external.invertexto_cpf import HttpInvertextoCpfValidator
from src.infrastructure.persistence.customer_public_lookup import (
    SqlAlchemyCustomerVehicleOwnershipLookup,
)
from src.infrastructure.persistence.customer_repository import SqlAlchemyCustomerRepository
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_customer_service(db: Session) -> CustomerService:
    return CustomerService(
        customers=SqlAlchemyCustomerRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
        cnpj_validator=HttpBrasilApiCnpjValidator(),
        cpf_validator=HttpInvertextoCpfValidator(token=settings.invertexto_api_token),
    )


def compose_customer_public_lookup_service(db: Session) -> CustomerPublicLookupService:
    return CustomerPublicLookupService(
        customers=SqlAlchemyCustomerRepository(db),
        vehicles=SqlAlchemyCustomerVehicleOwnershipLookup(db),
    )
