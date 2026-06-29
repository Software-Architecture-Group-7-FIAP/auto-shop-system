from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BudgetServiceProductRequirement:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class BudgetServiceDetails:
    id: int
    name: str
    base_price: float
    estimated_hours: float
    product_requirements: tuple[BudgetServiceProductRequirement, ...] = ()


@dataclass(frozen=True)
class BudgetProductDetails:
    id: int
    name: str
    unit_price: float
    stock_quantity: int


class VehicleOwnershipLookup(Protocol):
    def belongs_to_customer(self, vehicle_id: int, customer_id: int) -> bool:
        ...


class BudgetServiceCatalogLookup(Protocol):
    def get_service(self, service_id: int) -> BudgetServiceDetails | None:
        ...


class BudgetProductLookup(Protocol):
    def get_product(self, product_id: int) -> BudgetProductDetails | None:
        ...


class ReservationLookup(Protocol):
    def active_quantity_for_product(self, product_id: int) -> int:
        ...
