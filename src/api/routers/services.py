from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import (
    ServiceCreate,
    ServiceProductLineCreate,
    ServiceResponse,
    ServiceUpdate,
)
from src.application.services.service_catalog_service import ServiceCatalogService
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
        return ServiceCatalogService(db).create(
            data.name, data.description, data.base_price, data.estimated_hours
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("", response_model=list[ServiceResponse])
def list_services(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return ServiceCatalogService(db).list_all()


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ServiceCatalogService(db).get_by_id(service_id)
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
        return ServiceCatalogService(db).update(
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
        ServiceCatalogService(db).delete(service_id)
    except DomainError as e:
        raise domain_error_handler(e)


@router.post("/{service_id}/product-lines", status_code=201)
def add_product_line(
    service_id: int,
    data: ServiceProductLineCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        line = ServiceCatalogService(db).add_product_line(service_id, data.product_id, data.quantity)
        return {"id": line.id, "service_id": line.service_id, "product_id": line.product_id, "quantity": line.quantity}
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
        ServiceCatalogService(db).remove_product_line(service_id, line_id)
    except DomainError as e:
        raise domain_error_handler(e)
