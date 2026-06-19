from src.application.ports.unit_of_work import UnitOfWork
from src.domain.customer.entity import Customer
from src.domain.customer.repository import CustomerRepository
from src.domain.customer.value_objects import CustomerDocument
from src.domain.exceptions import ConflictError, NotFoundError


class CustomerService:
    def __init__(self, customers: CustomerRepository, uow: UnitOfWork):
        self.customers = customers
        self.uow = uow

    def create(
        self, name: str, document: str, email: str, phone: str | None = None
    ) -> Customer:
        customer = Customer.create(name=name, document=document, email=email, phone=phone)
        if self.customers.exists_by_document(customer.document):
            raise ConflictError("Cliente com este documento já existe")
        created = self.customers.add(customer)
        self.uow.commit()
        return created

    def get_by_id(self, customer_id: int) -> Customer:
        customer = self.customers.get_by_id(customer_id)
        if not customer:
            raise NotFoundError("Cliente não encontrado")
        return customer

    def get_by_document(self, document: str) -> Customer:
        customer = self.customers.get_by_document(CustomerDocument.create(document))
        if not customer:
            raise NotFoundError("Cliente não encontrado")
        return customer

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        return self.customers.list_all(skip, limit)

    def update(
        self, customer_id: int, name: str | None, email: str | None, phone: str | None
    ) -> Customer:
        customer = self.get_by_id(customer_id)
        customer.update_contact(name=name, email=email, phone=phone)
        updated = self.customers.save(customer)
        self.uow.commit()
        return updated

    def delete(self, customer_id: int) -> None:
        customer = self.get_by_id(customer_id)
        self.customers.delete(customer)
        self.uow.commit()
