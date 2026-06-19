from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import VehicleCreate, VehicleResponse, VehicleUpdate
from src.application.services.vehicle_service import VehicleService
from src.domain.exceptions import DomainError
from src.infrastructure.database import UserModel, get_db
from src.infrastructure.persistence.customer_repository import SqlAlchemyCustomerLookup
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.infrastructure.persistence.vehicle_repository import SqlAlchemyVehicleRepository

router = APIRouter(prefix="/admin/vehicles", tags=["Vehicles"])


def compose_vehicle_service(db: Session) -> VehicleService:
    return VehicleService(
        vehicles=SqlAlchemyVehicleRepository(db),
        customers=SqlAlchemyCustomerLookup(db),
        uow=SqlAlchemyUnitOfWork(db),
    )


@router.post("", response_model=VehicleResponse, status_code=201)
def create_vehicle(
    data: VehicleCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_vehicle_service(db).create(
            data.customer_id, data.plate, data.brand, data.model, data.year
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("", response_model=list[VehicleResponse])
def list_vehicles(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_vehicle_service(db).list_all()


@router.get("/customer/{customer_id}", response_model=list[VehicleResponse])
def list_customer_vehicles(
    customer_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_vehicle_service(db).list_by_customer(customer_id)


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_vehicle_service(db).get_by_id(vehicle_id)
    except DomainError as e:
        raise domain_error_handler(e)


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    data: VehicleUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_vehicle_service(db).update(vehicle_id, data.brand, data.model, data.year)
    except DomainError as e:
        raise domain_error_handler(e)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        compose_vehicle_service(db).delete(vehicle_id)
    except DomainError as e:
        raise domain_error_handler(e)
