import pytest

from src.domain.customer.entity import Customer
from src.domain.customer.value_objects import CustomerDocument
from src.domain.enums import PersonType
from src.domain.exceptions import ValidationError


def test_customer_document_normalizes_cpf():
    assert CustomerDocument.create("529.982.247-25") == "52998224725"


def test_customer_document_normalizes_cnpj():
    assert CustomerDocument.create("04.252.011/0001-10") == "04252011000110"


def test_customer_document_rejects_invalid_document():
    with pytest.raises(ValidationError, match="Cliente inválido"):
        CustomerDocument.create("123")


def test_customer_create_normalizes_document():
    customer = Customer.create(
        name="Maria Silva",
        person_type=PersonType.PF,
        document="529.982.247-25",
        email="maria@test.com",
        address="Rua A, 100",
        phone="11999999999",
    )

    assert customer.document == "52998224725"
    assert customer.person_type == PersonType.PF
    assert customer.name == "Maria Silva"
    assert customer.email == "maria@test.com"
    assert customer.phone == "11999999999"
    assert customer.address == "Rua A, 100"


def test_customer_create_pj_with_cnpj():
    customer = Customer.create(
        name="Empresa LTDA",
        person_type=PersonType.PJ,
        document="04.252.011/0001-10",
        email="empresa@test.com",
        address="Av. B, 200",
    )

    assert customer.person_type == PersonType.PJ
    assert customer.document == "04252011000110"


def test_customer_rejects_pf_with_cnpj():
    with pytest.raises(ValidationError, match="Cliente inválido"):
        Customer.create(
            name="Empresa LTDA",
            person_type=PersonType.PF,
            document="04.252.011/0001-10",
            email="empresa@test.com",
            address="Av. B, 200",
        )


def test_customer_rejects_pj_with_cpf():
    with pytest.raises(ValidationError, match="Cliente inválido"):
        Customer.create(
            name="Maria Silva",
            person_type=PersonType.PJ,
            document="529.982.247-25",
            email="maria@test.com",
            address="Rua A, 100",
        )


def test_customer_updates_only_provided_contact_fields():
    customer = Customer.create(
        name="Maria Silva",
        person_type=PersonType.PF,
        document="529.982.247-25",
        email="maria@test.com",
        address="Rua A, 100",
        phone="11999999999",
    )

    customer.update_contact(name="Maria S.", email=None, phone=None, address=None)

    assert customer.name == "Maria S."
    assert customer.email == "maria@test.com"
    assert customer.phone == "11999999999"
    assert customer.address == "Rua A, 100"

    customer.update_contact(name=None, email=None, phone=None, address="Rua C, 300")

    assert customer.address == "Rua C, 300"
