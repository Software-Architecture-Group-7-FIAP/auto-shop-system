from sqlalchemy.orm import Session

from src.infrastructure.database import VehicleModel


class SqlAlchemyCustomerVehicleOwnershipLookup:
    def __init__(self, db: Session):
        self.db = db

    def customer_owns_plate(self, customer_id: int, plate: str) -> bool:
        return (
            self.db.query(VehicleModel)
            .filter(VehicleModel.customer_id == customer_id, VehicleModel.plate == plate)
            .first()
            is not None
        )
