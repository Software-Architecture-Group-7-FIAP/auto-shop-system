from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from src.api.composition.billing import compose_invoice_service
from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import InvoiceResponse, PaymentCreate, ServiceOrderResponse
from src.domain.exceptions import DomainError
from src.infrastructure.database import UserModel, get_db

router = APIRouter(tags=["Invoices"])


@router.post("/admin/service-orders/{service_order_id}/invoice", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_invoice_service(db).create_invoice(service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("/admin/service-orders/{service_order_id}/invoice", response_model=InvoiceResponse)
def get_invoice_by_service_order(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_invoice_service(db).get_by_service_order_id(service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@router.patch("/admin/invoices/{invoice_id}/pay", response_model=InvoiceResponse)
def pay_invoice(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return compose_invoice_service(db).pay_invoice(invoice_id, actor_id=current_user.id, request_id=request.headers.get("x-request-id") or str(uuid4()))
    except DomainError as e:
            raise domain_error_handler(e)


@router.post("/admin/invoices/{invoice_id}/payments", response_model=InvoiceResponse)
def record_payment(
    invoice_id: int,
    data: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        key = idempotency_key.strip()
        if not key:
            raise ValueError("Idempotency-Key é obrigatória")
        if len(key) > 128:
            raise ValueError("Idempotency-Key excede o limite permitido")
        return compose_invoice_service(db).record_payment(
            invoice_id,
            amount=data.amount,
            method=data.method,
            actor_id=current_user.id,
            idempotency_key=key,
            request_id=key,
        )
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DomainError as e:
        raise domain_error_handler(e)


@router.patch("/admin/service-orders/{service_order_id}/deliver", response_model=ServiceOrderResponse)
def deliver_service_order(
    service_order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return compose_invoice_service(db).deliver(service_order_id, actor_id=current_user.id, request_id=request.headers.get("x-request-id") or str(uuid4()))
    except DomainError as e:
        raise domain_error_handler(e)
