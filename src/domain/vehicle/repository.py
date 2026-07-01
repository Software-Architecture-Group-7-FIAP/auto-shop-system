from typing import Protocol

from src.domain.vehicle.entity import Vehicle
from src.domain.vehicle.value_objects import Plate


class VehicleRepository(Protocol):
    def add(self, vehicle: Vehicle) -> Vehicle:
        ...

    def get_by_id(self, vehicle_id: int) -> Vehicle | None:
        ...

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Vehicle]:
        ...

    def list_by_customer(self, customer_id: int) -> list[Vehicle]:
        ...

    def exists_by_customer_and_plate(self, customer_id: int, plate: Plate) -> bool:
        ...

    def save(self, vehicle: Vehicle) -> Vehicle:
        ...

    def delete(self, vehicle: Vehicle) -> None:
        ...
