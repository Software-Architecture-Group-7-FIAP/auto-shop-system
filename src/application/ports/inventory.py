from dataclasses import dataclass
from typing import Protocol

from src.domain.enums import ServiceOrderStatus


@dataclass(frozen=True)
class InventoryProduct:
    id: int
    stock_quantity: int
    supplier_id: int | None = None


@dataclass(frozen=True)
class InventoryServiceOrderProductLine:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class InventoryServiceOrderSnapshot:
    id: int
    status: ServiceOrderStatus
    product_lines: tuple[InventoryServiceOrderProductLine, ...]


class InventoryProductGateway(Protocol):
    def get_product(self, product_id: int) -> InventoryProduct | None:
        ...

    def add_stock(self, product_id: int, quantity: int) -> None:
        ...

    def get_product_for_update(self, product_id: int) -> InventoryProduct | None:
        ...


class InventoryServiceOrderLookup(Protocol):
    def get_reservation_snapshot(
        self,
        service_order_id: int,
    ) -> InventoryServiceOrderSnapshot | None:
        ...

    def get_product_lines(
        self,
        service_order_id: int,
    ) -> list[InventoryServiceOrderProductLine] | None:
        ...

    def list_reservation_queue(
        self,
        product_id: int,
    ) -> list[InventoryServiceOrderSnapshot]:
        ...

    def set_reservation_status(
        self,
        service_order_id: int,
        status: ServiceOrderStatus,
    ) -> None:
        ...
