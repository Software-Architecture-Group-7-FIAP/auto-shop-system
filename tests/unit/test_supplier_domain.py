import pytest

from src.domain.exceptions import ValidationError
from src.domain.supplier.entity import Supplier
from src.domain.supplier.value_objects import SupplierDocument


def test_supplier_document_normalizes_cnpj():
    assert SupplierDocument.create("04.252.011/0001-10") == "04252011000110"


def test_supplier_document_rejects_invalid_document():
    with pytest.raises(ValidationError):
        SupplierDocument.create("123")


def test_supplier_create_normalizes_document():
    supplier = Supplier.create(
        name="Fornecedor A",
        document="04.252.011/0001-10",
        email="fornecedor@test.com",
        phone="11999999999",
    )

    assert supplier.document == "04252011000110"
    assert supplier.name == "Fornecedor A"
    assert supplier.email == "fornecedor@test.com"
    assert supplier.phone == "11999999999"


def test_supplier_updates_only_provided_contact_fields():
    supplier = Supplier.create(
        name="Fornecedor A",
        document="04.252.011/0001-10",
        email="fornecedor@test.com",
        phone="11999999999",
    )

    supplier.update_contact(name="Fornecedor B", email=None, phone=None)

    assert supplier.name == "Fornecedor B"
    assert supplier.email == "fornecedor@test.com"
    assert supplier.phone == "11999999999"
