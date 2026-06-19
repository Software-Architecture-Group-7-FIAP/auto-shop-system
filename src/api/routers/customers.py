from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.composition.customers import compose_customer_service
from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import (
    CnpjValidationResponse,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
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
        return compose_customer_service(db).create(
            data.name,
            data.person_type,
            data.document,
            data.email,
            data.address,
            data.phone,
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return compose_customer_service(db).list_all(skip, limit)


@router.get("/by-document/{document}", response_model=CustomerResponse)
def get_customer_by_document_admin(
    document: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        return compose_customer_service(db).get_by_document(document)
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("/validate-cnpj/{cnpj:path}", response_model=CnpjValidationResponse)
def validate_cnpj(
    cnpj: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        result = compose_customer_service(db).validate_cnpj(cnpj)
        return CnpjValidationResponse(
            valid=result.valid,
            legal_name=result.legal_name,
            trade_name=result.trade_name,
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        return compose_customer_service(db).get_by_id(customer_id)
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
        return compose_customer_service(db).update(
            customer_id, data.name, data.email, data.phone, data.address
        )
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
