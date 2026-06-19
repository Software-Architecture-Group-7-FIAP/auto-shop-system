from src.application.ports.customer_lookup import CustomerLookup
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.vehicle.entity import Vehicle
from src.domain.vehicle.repository import VehicleRepository


class VehicleService:
    def __init__(
        self,
        vehicles: VehicleRepository,
        customers: CustomerLookup,
        uow: UnitOfWork,
    ):
        self.vehicles = vehicles
        self.customers = customers
        self.uow = uow

    def create(
        self, customer_id: int, plate: str, brand: str, model: str, year: int
    ) -> Vehicle:
        if not self.customers.exists(customer_id):
            raise NotFoundError("Cliente não encontrado")

        vehicle = Vehicle.create(
            customer_id=customer_id,
            plate=plate,
            brand=brand,
            model=model,
            year=year,
        )
        if self.vehicles.exists_by_plate(vehicle.plate):
            raise ConflictError("Veículo com esta placa já existe")

        created = self.vehicles.add(vehicle)
        self.uow.commit()
        return created

    def get_by_id(self, vehicle_id: int) -> Vehicle:
        vehicle = self.vehicles.get_by_id(vehicle_id)
        if not vehicle:
            raise NotFoundError("Veículo não encontrado")
        return vehicle

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Vehicle]:
        return self.vehicles.list_all(skip, limit)

    def list_by_customer(self, customer_id: int) -> list[Vehicle]:
        return self.vehicles.list_by_customer(customer_id)

    def update(
        self,
        vehicle_id: int,
        brand: str | None,
        model: str | None,
        year: int | None,
    ) -> Vehicle:
        vehicle = self.get_by_id(vehicle_id)
        vehicle.update_details(brand, model, year)
        updated = self.vehicles.save(vehicle)
        self.uow.commit()
        return updated

    def delete(self, vehicle_id: int) -> None:
        vehicle = self.get_by_id(vehicle_id)
        self.vehicles.delete(vehicle)
        self.uow.commit()
