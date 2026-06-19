from typing import Protocol

from src.domain.supplier.entity import Supplier


class SupplierRepository(Protocol):
    def add(self, supplier: Supplier) -> Supplier:
        ...

    def get_by_id(self, supplier_id: int) -> Supplier | None:
        ...

    def list_all(self) -> list[Supplier]:
        ...

    def save(self, supplier: Supplier) -> Supplier:
        ...

    def delete(self, supplier: Supplier) -> None:
        ...
