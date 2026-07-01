from sqlalchemy.orm import Session

from src.application.services.customer_public_lookup_service import CustomerPublicLookupService
from src.application.services.customer_service import CustomerService
from src.config import settings
from src.infrastructure.external.brasil_api_cnpj import HttpBrasilApiCnpjValidator
from src.infrastructure.external.invertexto_cpf import HttpInvertextoCpfValidator
from src.infrastructure.external.local_cpf import LocalCpfValidator
from src.infrastructure.persistence.customer_public_lookup import (
    SqlAlchemyCustomerVehicleOwnershipLookup,
)
from src.infrastructure.persistence.customer_repository import SqlAlchemyCustomerRepository
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_customer_service(db: Session) -> CustomerService:
    cpf_validator = (
        LocalCpfValidator()
        if settings.skip_cpf_external_validation
        else (
            HttpInvertextoCpfValidator(token=settings.invertexto_api_token)
            if settings.invertexto_api_token
            else None
        )
    )
    return CustomerService(
        customers=SqlAlchemyCustomerRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
        cnpj_validator=HttpBrasilApiCnpjValidator(),
        cpf_validator=cpf_validator,
    )


def compose_customer_public_lookup_service(db: Session) -> CustomerPublicLookupService:
    return CustomerPublicLookupService(
        customers=SqlAlchemyCustomerRepository(db),
        vehicles=SqlAlchemyCustomerVehicleOwnershipLookup(db),
    )
