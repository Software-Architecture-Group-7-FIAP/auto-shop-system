from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import (
    AssignMechanicRequest,
    AverageExecutionTimeResponse,
    MessageResponse,
    ServiceOrderResponse,
    SetPriorityRequest,
)
from src.application.services.service_order_email_service import ServiceOrderEmailService
from src.application.services.service_order_service import ServiceOrderService
from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import DomainError
from src.infrastructure.database import UserModel, get_db

admin_router = APIRouter(prefix="/admin/service-orders", tags=["Service Orders"])
public_router = APIRouter(prefix="/public/service-orders", tags=["Public Service Orders"])


@admin_router.get("", response_model=list[ServiceOrderResponse])
def list_service_orders(
    status: ServiceOrderStatus | None = None,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return ServiceOrderService(db).list_all(status)


@admin_router.get("/metrics/average-execution-time", response_model=AverageExecutionTimeResponse)
def average_execution_time(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return ServiceOrderService(db).get_average_execution_time()


@admin_router.get("/in-progress/with-withdrawals", response_model=list[ServiceOrderResponse])
def list_os_with_withdrawals(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    from src.application.services.execution_service import ExecutionService
    return ExecutionService(db).list_os_with_withdrawals()


@admin_router.get("/{service_order_id}", response_model=ServiceOrderResponse)
def get_service_order(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ServiceOrderService(db).get_by_id(service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.patch("/{service_order_id}/assign-mechanic", response_model=ServiceOrderResponse)
def assign_mechanic(
    service_order_id: int,
    data: AssignMechanicRequest,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ServiceOrderService(db).assign_mechanic(service_order_id, data.mechanic_name)
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.patch("/{service_order_id}/priority", response_model=ServiceOrderResponse)
def set_priority(
    service_order_id: int,
    data: SetPriorityRequest,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ServiceOrderService(db).set_priority(service_order_id, data.priority)
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.post("/{service_order_id}/send-email", response_model=MessageResponse)
async def send_os_email(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        await ServiceOrderEmailService(db).send_os_email(service_order_id)
        return MessageResponse(message="Email da OS enviado.")
    except DomainError as e:
        raise domain_error_handler(e)


@public_router.get("/{service_order_id}", response_model=ServiceOrderResponse)
def track_service_order(
    service_order_id: int,
    document: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        return ServiceOrderService(db).get_by_customer_document(service_order_id, document)
    except DomainError as e:
        raise domain_error_handler(e)
