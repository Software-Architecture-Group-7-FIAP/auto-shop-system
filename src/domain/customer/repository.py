from typing import Protocol

from src.domain.customer.entity import Customer
from src.domain.customer.value_objects import Document


class CustomerRepository(Protocol):
    def add(self, customer: Customer) -> Customer:
        ...

    def get_by_id(self, customer_id: int) -> Customer | None:
        ...

    def get_by_document(self, document: Document) -> Customer | None:
        ...

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        ...

    def exists_by_document(self, document: Document) -> bool:
        ...

    def save(self, customer: Customer) -> Customer:
        ...

    def delete(self, customer: Customer) -> None:
        ...
