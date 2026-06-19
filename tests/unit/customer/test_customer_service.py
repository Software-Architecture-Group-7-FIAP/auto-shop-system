from dataclasses import replace

import pytest

from src.application.services.customer_service import CustomerService
from src.domain.customer.entity import Customer
from src.domain.customer.value_objects import CustomerDocument
from src.domain.exceptions import ConflictError, NotFoundError


class InMemoryCustomerRepository:
    def __init__(self):
        self.customers: dict[int, Customer] = {}
        self.next_id = 1

    def add(self, customer: Customer) -> Customer:
        created = replace(customer, id=self.next_id)
        self.customers[self.next_id] = created
        self.next_id += 1
        return created

    def get_by_id(self, customer_id: int) -> Customer | None:
        return self.customers.get(customer_id)

    def get_by_document(self, document: CustomerDocument) -> Customer | None:
        for customer in self.customers.values():
            if customer.document == document:
                return customer
        return None

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        return list(self.customers.values())[skip : skip + limit]

    def exists_by_document(self, document: CustomerDocument) -> bool:
        return self.get_by_document(document) is not None

    def save(self, customer: Customer) -> Customer:
        assert customer.id is not None
        self.customers[customer.id] = customer
        return customer

    def delete(self, customer: Customer) -> None:
        assert customer.id is not None
        del self.customers[customer.id]


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_customer_service_creates_customer_without_sqlalchemy():
    customers = InMemoryCustomerRepository()
    uow = FakeUnitOfWork()
    service = CustomerService(customers, uow)

    customer = service.create("Maria", "529.982.247-25", "maria@test.com")

    assert customer.id == 1
    assert customer.document == "52998224725"
    assert uow.commits == 1


def test_customer_service_rejects_duplicate_document():
    service = CustomerService(InMemoryCustomerRepository(), FakeUnitOfWork())
    service.create("Maria", "529.982.247-25", "maria@test.com")

    with pytest.raises(ConflictError):
        service.create("Maria 2", "52998224725", "maria2@test.com")


def test_customer_service_gets_customer_by_document():
    service = CustomerService(InMemoryCustomerRepository(), FakeUnitOfWork())
    service.create("Maria", "529.982.247-25", "maria@test.com")

    customer = service.get_by_document("52998224725")

    assert customer.email == "maria@test.com"


def test_customer_service_updates_customer_contact_fields():
    service = CustomerService(InMemoryCustomerRepository(), FakeUnitOfWork())
    customer = service.create("Maria", "529.982.247-25", "maria@test.com", "111")

    updated = service.update(customer.id, "Maria S.", None, "222")

    assert updated.name == "Maria S."
    assert updated.email == "maria@test.com"
    assert updated.phone == "222"


def test_customer_service_raises_when_customer_is_missing():
    service = CustomerService(InMemoryCustomerRepository(), FakeUnitOfWork())

    with pytest.raises(NotFoundError):
        service.get_by_id(1)
