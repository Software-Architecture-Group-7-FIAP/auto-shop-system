from dataclasses import replace

import pytest

from src.application.services.product_service import ProductService
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.product.entity import Product


class InMemoryProductRepository:
    def __init__(self):
        self.products: dict[int, Product] = {}
        self.next_id = 1

    def add(self, product: Product) -> Product:
        created = replace(product, id=self.next_id)
        self.products[self.next_id] = created
        self.next_id += 1
        return created

    def get_by_id(self, product_id: int) -> Product | None:
        return self.products.get(product_id)

    def list_all(self) -> list[Product]:
        return list(self.products.values())

    def exists_by_sku(self, sku: str) -> bool:
        return any(product.sku == sku for product in self.products.values())

    def save(self, product: Product) -> Product:
        assert product.id is not None
        self.products[product.id] = product
        return product

    def delete(self, product: Product) -> None:
        assert product.id is not None
        del self.products[product.id]


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_product_service_creates_product_without_sqlalchemy():
    products = InMemoryProductRepository()
    uow = FakeUnitOfWork()
    service = ProductService(products, uow)

    product = service.create("Óleo 5W30", "OLEO-001", 50.0, 10)

    assert product.id == 1
    assert product.sku == "OLEO-001"
    assert uow.commits == 1


def test_product_service_rejects_duplicate_sku():
    service = ProductService(InMemoryProductRepository(), FakeUnitOfWork())
    service.create("Óleo 5W30", "OLEO-001", 50.0, 10)

    with pytest.raises(ConflictError):
        service.create("Óleo 10W40", "OLEO-001", 60.0, 10)


def test_product_service_updates_product_details():
    service = ProductService(InMemoryProductRepository(), FakeUnitOfWork())
    product = service.create("Óleo 5W30", "OLEO-001", 50.0, 10)

    updated = service.update(product.id, "Filtro", 25.0, "Filtro de óleo", 2)

    assert updated.name == "Filtro"
    assert updated.sku == "OLEO-001"
    assert updated.unit_price == 25.0
    assert updated.description == "Filtro de óleo"
    assert updated.supplier_id == 2


def test_product_service_updates_stock():
    service = ProductService(InMemoryProductRepository(), FakeUnitOfWork())
    product = service.create("Óleo 5W30", "OLEO-001", 50.0, 10)

    updated = service.update_stock(product.id, -3)

    assert updated.stock_quantity == 7


def test_product_service_rejects_insufficient_stock():
    service = ProductService(InMemoryProductRepository(), FakeUnitOfWork())
    product = service.create("Óleo 5W30", "OLEO-001", 50.0, 10)

    with pytest.raises(ValidationError):
        service.update_stock(product.id, -11)


def test_product_service_raises_when_product_is_missing():
    service = ProductService(InMemoryProductRepository(), FakeUnitOfWork())

    with pytest.raises(NotFoundError):
        service.get_by_id(1)
