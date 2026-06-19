from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError
from src.domain.vehicle.entity import Vehicle
from src.domain.vehicle.value_objects import Plate
from src.infrastructure.database import VehicleModel


class SqlAlchemyVehicleRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, vehicle: Vehicle) -> Vehicle:
        model = VehicleModel(
            customer_id=vehicle.customer_id,
            plate=str(vehicle.plate),
            brand=vehicle.brand,
            model=vehicle.model,
            year=vehicle.year,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, vehicle_id: int) -> Vehicle | None:
        model = self.db.query(VehicleModel).filter(VehicleModel.id == vehicle_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Vehicle]:
        models = self.db.query(VehicleModel).offset(skip).limit(limit).all()
        return [self._to_domain(model) for model in models]

    def list_by_customer(self, customer_id: int) -> list[Vehicle]:
        models = (
            self.db.query(VehicleModel)
            .filter(VehicleModel.customer_id == customer_id)
            .all()
        )
        return [self._to_domain(model) for model in models]

    def exists_by_plate(self, plate: Plate) -> bool:
        return (
            self.db.query(VehicleModel)
            .filter(VehicleModel.plate == str(plate))
            .first()
            is not None
        )

    def save(self, vehicle: Vehicle) -> Vehicle:
        if vehicle.id is None:
            raise NotFoundError("Veículo não encontrado")

        model = self.db.query(VehicleModel).filter(VehicleModel.id == vehicle.id).first()
        if not model:
            raise NotFoundError("Veículo não encontrado")

        model.brand = vehicle.brand
        model.model = vehicle.model
        model.year = vehicle.year
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def delete(self, vehicle: Vehicle) -> None:
        if vehicle.id is None:
            raise NotFoundError("Veículo não encontrado")

        model = self.db.query(VehicleModel).filter(VehicleModel.id == vehicle.id).first()
        if not model:
            raise NotFoundError("Veículo não encontrado")

        self.db.delete(model)
        self.db.flush()

    @staticmethod
    def _to_domain(model: VehicleModel) -> Vehicle:
        return Vehicle(
            id=model.id,
            customer_id=model.customer_id,
            plate=Plate.create(model.plate),
            brand=model.brand,
            model=model.model,
            year=model.year,
            created_at=model.created_at,
        )
