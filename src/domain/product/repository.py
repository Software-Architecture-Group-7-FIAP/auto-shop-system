from typing import Protocol

from src.domain.product.entity import Product


class ProductRepository(Protocol):
    def add(self, product: Product) -> Product:
        ...

    def get_by_id(self, product_id: int) -> Product | None:
        ...

    def list_all(self) -> list[Product]:
        ...

    def exists_by_sku(self, sku: str) -> bool:
        ...

    def exists_by_supplier_id(self, supplier_id: int) -> bool:
        ...

    def save(self, product: Product) -> Product:
        ...

    def adjust_stock(self, product_id: int, quantity_delta: int) -> Product:
        ...

    def delete(self, product: Product) -> None:
        ...
