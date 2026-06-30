from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.composition.inventory import compose_inventory_service
from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import (
    GoodsReceiptCreate,
    PurchaseRequestCreate,
    PurchaseRequestResponse,
    ReservationCreate,
    ReservationResponse,
)
from src.domain.exceptions import DomainError
from src.infrastructure.database import UserModel, get_db

router = APIRouter(tags=["Inventory"])


@router.get("/admin/reservations", response_model=list[ReservationResponse])
def list_reservations(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_inventory_service(db).list_reservations()


@router.post("/admin/reservations", response_model=list[ReservationResponse], status_code=201)
def create_reservations(
    data: ReservationCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_inventory_service(db).create_reservations_for_os(data.service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@router.post(
    "/admin/reservations/os/{service_order_id}",
    response_model=list[ReservationResponse],
    status_code=201,
)
def create_reservations_for_os(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_inventory_service(db).create_reservations_for_os(service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("/admin/purchase-requests", response_model=list[PurchaseRequestResponse])
def list_purchase_requests(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_inventory_service(db).list_purchase_requests()


@router.post("/admin/purchase-requests", response_model=PurchaseRequestResponse, status_code=201)
def create_purchase_request(
    data: PurchaseRequestCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_inventory_service(db).create_purchase_request(
            data.product_id, data.quantity, data.service_order_id
        )
    except DomainError as e:
        raise domain_error_handler(e)


@router.post("/admin/purchase-requests/{purchase_request_id}/receipt", status_code=201)
def register_receipt(
    purchase_request_id: int,
    data: GoodsReceiptCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        receipt = compose_inventory_service(db).register_receipt(
            purchase_request_id,
            data.quantity,
        )
        return {"id": receipt.id, "purchase_request_id": receipt.purchase_request_id, "quantity": receipt.quantity}
    except DomainError as e:
        raise domain_error_handler(e)


@router.get("/admin/products/{product_id}/pending-receipts", response_model=list[PurchaseRequestResponse])
def get_pending_receipts(
    product_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_inventory_service(db).get_pending_receipts(product_id)
