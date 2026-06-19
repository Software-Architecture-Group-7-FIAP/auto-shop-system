import pytest

from src.domain.customer.entity import Customer
from src.domain.customer.value_objects import CustomerDocument
from src.domain.exceptions import ValidationError


def test_customer_document_normalizes_cpf():
    assert CustomerDocument.create("529.982.247-25") == "52998224725"


def test_customer_document_normalizes_cnpj():
    assert CustomerDocument.create("04.252.011/0001-10") == "04252011000110"


def test_customer_document_rejects_invalid_document():
    with pytest.raises(ValidationError):
        CustomerDocument.create("123")


def test_customer_create_normalizes_document():
    customer = Customer.create(
        name="Maria Silva",
        document="529.982.247-25",
        email="maria@test.com",
        phone="11999999999",
    )

    assert customer.document == "52998224725"
    assert customer.name == "Maria Silva"
    assert customer.email == "maria@test.com"
    assert customer.phone == "11999999999"


def test_customer_updates_only_provided_contact_fields():
    customer = Customer.create(
        name="Maria Silva",
        document="529.982.247-25",
        email="maria@test.com",
        phone="11999999999",
    )

    customer.update_contact(name="Maria S.", email=None, phone=None)

    assert customer.name == "Maria S."
    assert customer.email == "maria@test.com"
    assert customer.phone == "11999999999"
