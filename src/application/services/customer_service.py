from src.application.ports.cnpj_validator import CnpjExternalValidator, CnpjValidationResult
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.customer.entity import Customer
from src.domain.customer.repository import CustomerRepository
from src.domain.customer.value_objects import CustomerDocument
from src.domain.enums import PersonType
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError


class CustomerService:
    def __init__(
        self,
        customers: CustomerRepository,
        uow: UnitOfWork,
        cnpj_validator: CnpjExternalValidator | None = None,
    ):
        self.customers = customers
        self.uow = uow
        self.cnpj_validator = cnpj_validator

    def create(
        self,
        name: str,
        person_type: PersonType,
        document: str,
        email: str,
        address: str,
        phone: str | None = None,
    ) -> Customer:
        customer = Customer.create(
            name=name,
            person_type=person_type,
            document=document,
            email=email,
            address=address,
            phone=phone,
        )
        if person_type == PersonType.PJ:
            self._validate_cnpj_externally(str(customer.document))
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
        self,
        customer_id: int,
        name: str | None,
        email: str | None,
        phone: str | None,
        address: str | None,
    ) -> Customer:
        customer = self.get_by_id(customer_id)
        customer.update_contact(name=name, email=email, phone=phone, address=address)
        updated = self.customers.save(customer)
        self.uow.commit()
        return updated

    def delete(self, customer_id: int) -> None:
        customer = self.get_by_id(customer_id)
        self.customers.delete(customer)
        self.uow.commit()

    def validate_cnpj(self, document: str) -> CnpjValidationResult:
        customer_document = CustomerDocument.create(document)
        if len(customer_document) != 14:
            raise ValidationError("Cliente inválido")
        return self._validate_cnpj_externally(customer_document)

    def _validate_cnpj_externally(self, cnpj: str) -> CnpjValidationResult:
        if self.cnpj_validator is None:
            raise ValidationError("Serviço de validação de CNPJ indisponível")
        return self.cnpj_validator.validate(cnpj)
