import pytest

from src.domain.exceptions import ValidationError
from src.domain.product.entity import Product


def test_product_create_preserves_fields():
    product = Product.create(
        name="Óleo 5W30",
        sku="OLEO-001",
        unit_price=50.0,
        stock_quantity=10,
        description="Lubrificante",
        supplier_id=1,
    )

    assert product.name == "Óleo 5W30"
    assert product.sku == "OLEO-001"
    assert product.unit_price == 50.0
    assert product.stock_quantity == 10
    assert product.description == "Lubrificante"
    assert product.supplier_id == 1


def test_product_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        Product.create("Óleo 5W30", "OLEO-001", 0, 10)


def test_product_rejects_negative_initial_stock():
    with pytest.raises(ValidationError):
        Product.create("Óleo 5W30", "OLEO-001", 50.0, -1, supplier_id=1)


def test_product_rejects_missing_supplier():
    with pytest.raises(ValidationError):
        Product.create("Óleo 5W30", "OLEO-001", 50.0, 10)


def test_product_updates_details_and_stock():
    product = Product.create("Óleo 5W30", "OLEO-001", 50.0, 10, supplier_id=1)

    product.update_details("Filtro", 25.0, "Filtro de óleo", 2)
    product.update_stock(-3)

    assert product.name == "Filtro"
    assert product.sku == "OLEO-001"
    assert product.unit_price == 25.0
    assert product.description == "Filtro de óleo"
    assert product.supplier_id == 2
    assert product.stock_quantity == 7


def test_product_rejects_negative_final_stock():
    product = Product.create("Óleo 5W30", "OLEO-001", 50.0, 10, supplier_id=1)

    with pytest.raises(ValidationError):
        product.update_stock(-11)
