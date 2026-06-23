from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.composition.service_catalog import compose_service_catalog_service
from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import (
    ServiceCreate,
    ServiceProductLineCreate,
    ServiceProductLineDelete,
    ServiceProductLineResponse,
    ServiceResponse,
    ServiceUpdate,
)
from src.domain.exceptions import DomainError
from src.infrastructure.database import UserModel, get_db

router = APIRouter(prefix="/admin/services", tags=["Services"])


@router.post("", response_model=ServiceResponse, status_code=201)
def create_service(
    data: ServiceCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_service_catalog_service(db).create(
            data.name, data.description, data.base_price, data.estimated_hours
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("", response_model=list[ServiceResponse])
def list_services(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_service_catalog_service(db).list_all()


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_service_catalog_service(db).get_by_id(service_id)
    except DomainError as e:
        raise domain_error_handler(e)


@router.put("/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: int,
    data: ServiceUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_service_catalog_service(db).update(
            service_id, data.name, data.description, data.base_price, data.estimated_hours
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.delete("/{service_id}", status_code=204)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        compose_service_catalog_service(db).delete(service_id)
    except DomainError as e:
        raise domain_error_handler(e)


@router.post(
    "/{service_id}/product-lines",
    response_model=ServiceProductLineResponse,
    status_code=201,
)
def add_product_line(
    service_id: int,
    data: ServiceProductLineCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_service_catalog_service(db).add_product_line(
            service_id,
            data.product_id,
            data.quantity,
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.delete("/{service_id}/product-lines", status_code=204)
def remove_product_line_by_product(
    service_id: int,
    data: ServiceProductLineDelete,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        compose_service_catalog_service(db).remove_product_line_by_product(
            service_id,
            data.product_id,
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.delete("/{service_id}/product-lines/{line_id}", status_code=204)
def remove_product_line(
    service_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        compose_service_catalog_service(db).remove_product_line(service_id, line_id)
    except DomainError as e:
        raise domain_error_handler(e)
