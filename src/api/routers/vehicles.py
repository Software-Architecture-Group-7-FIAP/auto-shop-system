from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.composition.vehicles import compose_vehicle_service
from src.api.dependencies import domain_error_handler, get_current_user
from src.api.mappers.vehicles import vehicle_to_response
from src.api.schemas import VehicleCreate, VehicleResponse, VehicleUpdate
from src.domain.auth.entity import User
from src.domain.exceptions import DomainError
from src.infrastructure.database import get_db

router = APIRouter(prefix="/admin/vehicles", tags=["Vehicles"])


@router.post("", response_model=VehicleResponse, status_code=201)
def create_vehicle(
    data: VehicleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        vehicle = compose_vehicle_service(db).create(
            data.customer_id,
            data.plate,
            data.state,
            data.city,
            data.color,
            data.brand,
            data.model,
            data.year,
        )
        return vehicle_to_response(vehicle)
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("", response_model=list[VehicleResponse])
def list_vehicles(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    vehicles = compose_vehicle_service(db).list_all()
    return [vehicle_to_response(vehicle) for vehicle in vehicles]


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        vehicle = compose_vehicle_service(db).get_by_id(vehicle_id)
        return vehicle_to_response(vehicle)
    except DomainError as e:
        raise domain_error_handler(e)


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    data: VehicleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        vehicle = compose_vehicle_service(db).update(
            vehicle_id,
            data.state,
            data.city,
            data.color,
            data.brand,
            data.model,
            data.year,
        )
        return vehicle_to_response(vehicle)
    except DomainError as e:
        raise domain_error_handler(e)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        compose_vehicle_service(db).delete(vehicle_id)
    except DomainError as e:
        raise domain_error_handler(e)
