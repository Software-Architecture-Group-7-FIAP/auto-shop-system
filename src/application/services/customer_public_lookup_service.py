from dataclasses import dataclass
import re

from src.application.ports.customer_public_lookup import CustomerVehicleOwnershipLookup
from src.domain.customer.entity import Customer
from src.domain.customer.repository import CustomerRepository
from src.domain.customer.value_objects import Document
from src.domain.exceptions import NotFoundError, DomainError
from src.domain.value_objects.validators import PlateValidator


GENERIC_LOOKUP_ERROR = "Cliente não encontrado"


@dataclass(frozen=True)
class CustomerPublicLookupCriteria:
    document: str
    email: str | None = None
    phone: str | None = None
    plate: str | None = None


class CustomerPublicLookupService:
    def __init__(
        self,
        customers: CustomerRepository,
        vehicles: CustomerVehicleOwnershipLookup,
    ):
        self.customers = customers
        self.vehicles = vehicles

    def lookup(self, criteria: CustomerPublicLookupCriteria) -> Customer:
        try:
            customer = self.customers.get_by_document(Document.create(criteria.document))
        except DomainError as exc:
            raise NotFoundError(GENERIC_LOOKUP_ERROR) from exc
        if not customer or customer.id is None:
            raise NotFoundError(GENERIC_LOOKUP_ERROR)
        if not self._matches_second_factor(customer, criteria):
            raise NotFoundError(GENERIC_LOOKUP_ERROR)
        return customer

    def _matches_second_factor(
        self,
        customer: Customer,
        criteria: CustomerPublicLookupCriteria,
    ) -> bool:
        if customer.id is None:
            return False
        if criteria.email is not None and customer.email.lower() == criteria.email.lower():
            return True
        if criteria.phone is not None and customer.phone is not None:
            return _digits(customer.phone) == _digits(criteria.phone)
        if criteria.plate is not None:
            try:
                plate = PlateValidator.validate(criteria.plate)
            except DomainError:
                return False
            return self.vehicles.customer_owns_plate(customer.id, plate)
        return False


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)
