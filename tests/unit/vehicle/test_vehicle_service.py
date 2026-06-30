from dataclasses import replace

import pytest

from src.application.services.vehicle_service import VehicleService
from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.vehicle.entity import Vehicle
from src.domain.vehicle.value_objects import Plate


class InMemoryVehicleRepository:
    def __init__(self):
        self.vehicles: dict[int, Vehicle] = {}
        self.next_id = 1

    def add(self, vehicle: Vehicle) -> Vehicle:
        created = replace(vehicle, id=self.next_id)
        self.vehicles[self.next_id] = created
        self.next_id += 1
        return created

    def get_by_id(self, vehicle_id: int) -> Vehicle | None:
        return self.vehicles.get(vehicle_id)

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Vehicle]:
        return list(self.vehicles.values())[skip : skip + limit]

    def list_by_customer(self, customer_id: int) -> list[Vehicle]:
        return [
            vehicle
            for vehicle in self.vehicles.values()
            if vehicle.customer_id == customer_id
        ]

    def exists_by_customer_and_plate(self, customer_id: int, plate: Plate) -> bool:
        return any(
            vehicle.customer_id == customer_id and vehicle.plate == plate
            for vehicle in self.vehicles.values()
        )

    def save(self, vehicle: Vehicle) -> Vehicle:
        assert vehicle.id is not None
        self.vehicles[vehicle.id] = vehicle
        return vehicle

    def delete(self, vehicle: Vehicle) -> None:
        assert vehicle.id is not None
        del self.vehicles[vehicle.id]


class InMemoryCustomerLookup:
    def __init__(self, existing_ids: set[int]):
        self.existing_ids = existing_ids

    def exists(self, customer_id: int) -> bool:
        return customer_id in self.existing_ids


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _vehicle_kwargs(**overrides):
    base = {
        "plate": "abc-1234",
        "state": "sp",
        "city": "São Paulo",
        "color": "Preto",
        "brand": "Fiat",
        "model": "Uno",
        "year": 2020,
    }
    base.update(overrides)
    return base


def test_vehicle_service_creates_vehicle_without_sqlalchemy():
    vehicles = InMemoryVehicleRepository()
    uow = FakeUnitOfWork()
    service = VehicleService(vehicles, InMemoryCustomerLookup({1}), uow)

    vehicle = service.create(1, **_vehicle_kwargs())

    assert vehicle.id == 1
    assert vehicle.plate == "ABC1234"
    assert vehicle.state == "SP"
    assert vehicle.city == "São Paulo"
    assert vehicle.color == "Preto"
    assert uow.commits == 1


def test_vehicle_service_rejects_unknown_customer():
    service = VehicleService(
        InMemoryVehicleRepository(),
        InMemoryCustomerLookup(set()),
        FakeUnitOfWork(),
    )

    with pytest.raises(NotFoundError):
        service.create(1, **_vehicle_kwargs())


def test_vehicle_service_rejects_duplicate_plate_for_same_customer():
    vehicles = InMemoryVehicleRepository()
    service = VehicleService(vehicles, InMemoryCustomerLookup({1}), FakeUnitOfWork())
    service.create(1, **_vehicle_kwargs())

    with pytest.raises(ConflictError, match="já existe para o cliente"):
        service.create(1, **_vehicle_kwargs(brand="VW", model="Gol", year=2021))


def test_vehicle_service_allows_same_plate_for_different_customers():
    vehicles = InMemoryVehicleRepository()
    service = VehicleService(vehicles, InMemoryCustomerLookup({1, 2}), FakeUnitOfWork())
    service.create(1, **_vehicle_kwargs())

    vehicle = service.create(2, **_vehicle_kwargs())

    assert vehicle.customer_id == 2
    assert vehicle.plate == "ABC1234"


def test_vehicle_service_list_by_customer_requires_existing_customer():
    service = VehicleService(
        InMemoryVehicleRepository(),
        InMemoryCustomerLookup(set()),
        FakeUnitOfWork(),
    )

    with pytest.raises(NotFoundError, match="Cliente não encontrado"):
        service.list_by_customer(1)
