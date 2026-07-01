from sqlalchemy.orm import Session

from src.application.services.vehicle_service import VehicleService
from src.infrastructure.persistence.customer_repository import SqlAlchemyCustomerLookup
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.infrastructure.persistence.vehicle_repository import SqlAlchemyVehicleRepository


def compose_vehicle_service(db: Session) -> VehicleService:
    return VehicleService(
        vehicles=SqlAlchemyVehicleRepository(db),
        customers=SqlAlchemyCustomerLookup(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
