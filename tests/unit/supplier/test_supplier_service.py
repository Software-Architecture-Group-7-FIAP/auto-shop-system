from dataclasses import replace

import pytest

from src.application.services.product_service import SupplierService
from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.product.entity import Product
from src.domain.supplier.entity import Supplier


class InMemorySupplierRepository:
    def __init__(self):
        self.suppliers: dict[int, Supplier] = {}
        self.next_id = 1

    def add(self, supplier: Supplier) -> Supplier:
        created = replace(supplier, id=self.next_id)
        self.suppliers[self.next_id] = created
        self.next_id += 1
        return created

    def get_by_id(self, supplier_id: int) -> Supplier | None:
        return self.suppliers.get(supplier_id)

    def list_all(self) -> list[Supplier]:
        return list(self.suppliers.values())

    def save(self, supplier: Supplier) -> Supplier:
        assert supplier.id is not None
        self.suppliers[supplier.id] = supplier
        return supplier

    def delete(self, supplier: Supplier) -> None:
        assert supplier.id is not None
        del self.suppliers[supplier.id]


class InMemoryProductRepository:
    def __init__(self):
        self.products: dict[int, Product] = {}

    def exists_by_supplier_id(self, supplier_id: int) -> bool:
        return any(product.supplier_id == supplier_id for product in self.products.values())


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_supplier_service_creates_supplier_without_sqlalchemy():
    suppliers = InMemorySupplierRepository()
    products = InMemoryProductRepository()
    uow = FakeUnitOfWork()
    service = SupplierService(suppliers, products, uow)

    supplier = service.create(
        "Fornecedor A",
        "04.252.011/0001-10",
        "fornecedor@test.com",
    )

    assert supplier.id == 1
    assert supplier.document == "04252011000110"
    assert uow.commits == 1


def test_supplier_service_updates_supplier_contact_fields():
    service = SupplierService(
        InMemorySupplierRepository(),
        InMemoryProductRepository(),
        FakeUnitOfWork(),
    )
    supplier = service.create(
        "Fornecedor A",
        "04.252.011/0001-10",
        "fornecedor@test.com",
        "111",
    )

    updated = service.update(supplier.id, "Fornecedor B", None, "222")

    assert updated.name == "Fornecedor B"
    assert updated.email == "fornecedor@test.com"
    assert updated.phone == "222"


def test_supplier_service_raises_when_supplier_is_missing():
    service = SupplierService(
        InMemorySupplierRepository(),
        InMemoryProductRepository(),
        FakeUnitOfWork(),
    )

    with pytest.raises(NotFoundError):
        service.get_by_id(1)


def test_supplier_service_rejects_delete_when_supplier_has_products():
    suppliers = InMemorySupplierRepository()
    products = InMemoryProductRepository()
    service = SupplierService(suppliers, products, FakeUnitOfWork())
    supplier = service.create("Fornecedor A", "04.252.011/0001-10", "fornecedor@test.com")
    products.products[1] = Product.create("Óleo", "OLEO-001", 50.0, 10, supplier_id=supplier.id)

    with pytest.raises(ConflictError):
        service.delete(supplier.id)
