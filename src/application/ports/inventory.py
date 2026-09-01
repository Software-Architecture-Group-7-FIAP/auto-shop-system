from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InventoryProduct:
    id: int
    stock_quantity: int
    supplier_id: int | None = None


@dataclass(frozen=True)
class InventoryServiceOrderProductLine:
    product_id: int
    quantity: int


class InventoryProductGateway(Protocol):
    def get_product(self, product_id: int) -> InventoryProduct | None:
        ...

    def add_stock(self, product_id: int, quantity: int) -> None:
        ...


class InventoryServiceOrderLookup(Protocol):
    def get_product_lines(
        self,
        service_order_id: int,
    ) -> list[InventoryServiceOrderProductLine] | None:
        ...
