from sqlalchemy.orm import Session

from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.value_objects.validators import PlateValidator
from src.infrastructure.database import CustomerModel, VehicleModel


class VehicleService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, customer_id: int, plate: str, brand: str, model: str, year: int
    ) -> VehicleModel:
        customer = self.db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        if not customer:
            raise NotFoundError("Cliente não encontrado")
        normalized_plate = PlateValidator.validate(plate)
        existing = self.db.query(VehicleModel).filter(VehicleModel.plate == normalized_plate).first()
        if existing:
            raise ConflictError("Veículo com esta placa já existe")
        vehicle = VehicleModel(
            customer_id=customer_id,
            plate=normalized_plate,
            brand=brand,
            model=model,
            year=year,
        )
        self.db.add(vehicle)
        self.db.commit()
        self.db.refresh(vehicle)
        return vehicle

    def get_by_id(self, vehicle_id: int) -> VehicleModel:
        vehicle = self.db.query(VehicleModel).filter(VehicleModel.id == vehicle_id).first()
        if not vehicle:
            raise NotFoundError("Veículo não encontrado")
        return vehicle

    def list_all(self, skip: int = 0, limit: int = 100) -> list[VehicleModel]:
        return self.db.query(VehicleModel).offset(skip).limit(limit).all()

    def list_by_customer(self, customer_id: int) -> list[VehicleModel]:
        return self.db.query(VehicleModel).filter(VehicleModel.customer_id == customer_id).all()

    def update(
        self,
        vehicle_id: int,
        brand: str | None,
        model: str | None,
        year: int | None,
    ) -> VehicleModel:
        vehicle = self.get_by_id(vehicle_id)
        if brand is not None:
            vehicle.brand = brand
        if model is not None:
            vehicle.model = model
        if year is not None:
            vehicle.year = year
        self.db.commit()
        self.db.refresh(vehicle)
        return vehicle

    def delete(self, vehicle_id: int) -> None:
        vehicle = self.get_by_id(vehicle_id)
        self.db.delete(vehicle)
        self.db.commit()
