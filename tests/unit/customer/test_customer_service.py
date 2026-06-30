from dataclasses import replace

import pytest

from src.application.ports.cnpj_validator import CnpjValidationResult
from src.application.ports.cpf_validator import CpfValidationResult
from src.application.services.customer_service import CustomerService
from src.domain.customer.entity import Customer
from src.domain.customer.value_objects import Document
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError


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

    def get_by_document(self, document: Document) -> Customer | None:
        for customer in self.customers.values():
            if customer.has_document(document):
                return customer
        return None

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        return list(self.customers.values())[skip : skip + limit]

    def exists_by_document(self, document: Document) -> bool:
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


class FakeCnpjValidator:
    def __init__(self, result: CnpjValidationResult | None = None):
        self.result = result or CnpjValidationResult(
            valid=True,
            legal_name="Empresa LTDA",
            trade_name="Empresa",
        )
        self.calls: list[str] = []

    def validate(self, cnpj: str) -> CnpjValidationResult:
        self.calls.append(cnpj)
        return self.result


class FakeCpfValidator:
    def __init__(self, result: CpfValidationResult | None = None):
        self.result = result or CpfValidationResult(
            valid=True,
            formatted="529.982.247-25",
        )
        self.calls: list[str] = []

    def validate(self, cpf: str) -> CpfValidationResult:
        self.calls.append(cpf)
        return self.result


def _pf_payload(**overrides):
    data = {
        "name": "Maria",
        "document": "529.982.247-25",
        "email": "maria@test.com",
        "address": "Rua A, 100",
    }
    data.update(overrides)
    return data


def test_customer_service_creates_customer_without_sqlalchemy():
    customers = InMemoryCustomerRepository()
    uow = FakeUnitOfWork()
    service = CustomerService(customers, uow, cpf_validator=FakeCpfValidator())

    customer = service.create(**_pf_payload())

    assert customer.id == 1
    assert customer.documents == ["52998224725"]
    assert customer.address == "Rua A, 100"
    assert uow.commits == 1


def test_customer_service_rejects_duplicate_document():
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cpf_validator=FakeCpfValidator(),
    )
    service.create(**_pf_payload())

    with pytest.raises(ConflictError):
        service.create(**_pf_payload(name="Maria 2", email="maria2@test.com"))


def test_customer_service_checks_duplicate_before_external_cnpj_validation():
    cnpj_validator = FakeCnpjValidator()
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cnpj_validator=cnpj_validator,
    )
    service.create(
        name="Empresa LTDA",
        document="04.252.011/0001-10",
        email="empresa@test.com",
        address="Av. B, 200",
    )

    with pytest.raises(ConflictError):
        service.create(
            name="Empresa 2 LTDA",
            document="04.252.011/0001-10",
            email="empresa2@test.com",
            address="Av. C, 300",
        )

    assert cnpj_validator.calls == ["04252011000110"]


def test_customer_service_gets_customer_by_document():
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cpf_validator=FakeCpfValidator(),
    )
    service.create(**_pf_payload())

    customer = service.get_by_document("52998224725")

    assert customer.email == "maria@test.com"


def test_customer_service_updates_customer_contact_fields():
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cpf_validator=FakeCpfValidator(),
    )
    customer = service.create(**_pf_payload(phone="111"))

    updated = service.update(customer.id, "Maria S.", None, "222", "Rua B, 200")

    assert updated.name == "Maria S."
    assert updated.email == "maria@test.com"
    assert updated.phone == "222"
    assert updated.address == "Rua B, 200"


def test_customer_service_adds_document_to_existing_customer():
    cnpj_validator = FakeCnpjValidator()
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cnpj_validator=cnpj_validator,
    )
    customer = service.create(
        name="Empresa LTDA",
        document="04.252.011/0001-10",
        email="empresa@test.com",
        address="Av. B, 200",
    )

    updated = service.add_document(customer.id, "11.444.777/0001-61")

    assert len(updated.documents) == 2
    assert cnpj_validator.calls == ["04252011000110", "11444777000161"]


def test_customer_service_raises_when_customer_is_missing():
    service = CustomerService(InMemoryCustomerRepository(), FakeUnitOfWork())

    with pytest.raises(NotFoundError):
        service.get_by_id(1)


def test_customer_service_creates_pj_with_external_cnpj_validation():
    cnpj_validator = FakeCnpjValidator()
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cnpj_validator=cnpj_validator,
    )

    customer = service.create(
        name="Empresa LTDA",
        document="04.252.011/0001-10",
        email="empresa@test.com",
        address="Av. B, 200",
    )

    assert customer.documents == ["04252011000110"]
    assert cnpj_validator.calls == ["04252011000110"]


def test_customer_service_validate_cnpj_delegates_to_external_validator():
    cnpj_validator = FakeCnpjValidator()
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cnpj_validator=cnpj_validator,
    )

    result = service.validate_cnpj("04.252.011/0001-10")

    assert result.valid is True
    assert result.legal_name == "Empresa LTDA"
    assert cnpj_validator.calls == ["04252011000110"]


def test_customer_service_validate_cnpj_rejects_cpf():
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cnpj_validator=FakeCnpjValidator(),
    )

    with pytest.raises(ValidationError, match="CNPJ inválido"):
        service.validate_cnpj("529.982.247-25")


def test_customer_service_creates_pf_with_external_cpf_validation():
    cpf_validator = FakeCpfValidator()
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cpf_validator=cpf_validator,
    )

    customer = service.create(**_pf_payload())

    assert customer.documents == ["52998224725"]
    assert cpf_validator.calls == ["52998224725"]


def test_customer_service_creates_pf_without_external_cpf_validator():
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
    )

    customer = service.create(**_pf_payload())

    assert customer.documents == ["52998224725"]


def test_customer_service_checks_duplicate_before_external_cpf_validation():
    cpf_validator = FakeCpfValidator()
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cpf_validator=cpf_validator,
    )
    service.create(**_pf_payload())

    with pytest.raises(ConflictError):
        service.create(**_pf_payload(name="Maria 2", email="maria2@test.com"))

    assert cpf_validator.calls == ["52998224725"]


def test_customer_service_validate_cpf_delegates_to_external_validator():
    cpf_validator = FakeCpfValidator()
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cpf_validator=cpf_validator,
    )

    result = service.validate_cpf("529.982.247-25")

    assert result.valid is True
    assert result.formatted == "529.982.247-25"
    assert cpf_validator.calls == ["52998224725"]


def test_customer_service_validate_cpf_accepts_structural_validation_without_external_validator():
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
    )

    result = service.validate_cpf("529.982.247-25")

    assert result.valid is True
    assert result.formatted == "52998224725"


def test_customer_service_validate_cpf_rejects_cnpj():
    service = CustomerService(
        InMemoryCustomerRepository(),
        FakeUnitOfWork(),
        cpf_validator=FakeCpfValidator(),
    )

    with pytest.raises(ValidationError, match="CPF inválido"):
        service.validate_cpf("04.252.011/0001-10")
