from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.composition.customers import compose_customer_service
from src.api.composition.vehicles import compose_vehicle_service
from src.api.dependencies import domain_error_handler, get_current_user
from src.api.mappers.customers import customer_to_response
from src.api.mappers.vehicles import vehicle_to_response
from src.api.schemas import (
    CnpjValidationResponse,
    CpfValidationResponse,
    CustomerCreate,
    CustomerDocumentLookupRequest,
    CustomerDocumentAdd,
    CustomerResponse,
    CustomerUpdate,
    DocumentValidationRequest,
    VehicleResponse,
)
from src.domain.auth.entity import User
from src.domain.exceptions import DomainError
from src.infrastructure.database import get_db

router = APIRouter(prefix="/admin/customers", tags=["Customers"])


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        customer = compose_customer_service(db).create(
            data.name,
            data.document,
            data.email,
            data.address,
            data.phone,
        )
        return customer_to_response(customer)
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    customers = compose_customer_service(db).list_all(skip, limit)
    return [customer_to_response(customer) for customer in customers]


@router.post("/by-document", response_model=CustomerResponse)
def get_customer_by_document_admin(
    data: CustomerDocumentLookupRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        customer = compose_customer_service(db).get_by_document(data.document)
        return customer_to_response(customer)
    except DomainError as e:
        raise domain_error_handler(e)


@router.post("/validate-cnpj", response_model=CnpjValidationResponse)
def validate_cnpj(
    data: DocumentValidationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        result = compose_customer_service(db).validate_cnpj(data.document)
        return CnpjValidationResponse(
            valid=result.valid,
            legal_name=result.legal_name,
            trade_name=result.trade_name,
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.post("/validate-cpf", response_model=CpfValidationResponse)
def validate_cpf(
    data: DocumentValidationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        result = compose_customer_service(db).validate_cpf(data.document)
        return CpfValidationResponse(
            valid=result.valid,
            formatted=result.formatted,
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("/{customer_id}/vehicles", response_model=list[VehicleResponse])
def list_customer_vehicles(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        vehicles = compose_vehicle_service(db).list_by_customer(customer_id)
        return [vehicle_to_response(vehicle) for vehicle in vehicles]
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        customer = compose_customer_service(db).get_by_id(customer_id)
        return customer_to_response(customer)
    except DomainError as e:
        raise domain_error_handler(e)


@router.post("/{customer_id}/documents", response_model=CustomerResponse)
def add_customer_document(
    customer_id: int,
    data: CustomerDocumentAdd,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        customer = compose_customer_service(db).add_document(customer_id, data.document)
        return customer_to_response(customer)
    except DomainError as e:
        raise domain_error_handler(e)


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        customer = compose_customer_service(db).update(
            customer_id, data.name, data.email, data.phone, data.address
        )
        return customer_to_response(customer)
    except DomainError as e:
        raise domain_error_handler(e)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        compose_customer_service(db).delete(customer_id)
    except DomainError as e:
        raise domain_error_handler(e)
