from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.composition.service_orders import (
    compose_service_order_email_service,
    compose_service_order_service,
)
from src.api.composition.execution import compose_execution_service
from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import (
    AssignMechanicRequest,
    AverageExecutionTimeResponse,
    MessageResponse,
    OverrideStatusRequest,
    ServiceOrderPublicResponse,
    ServiceOrderResponse,
    ServiceOrderUpdate,
    SetPriorityRequest,
)
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
    return compose_service_order_service(db).list_all(status)


@admin_router.get("/metrics/average-execution-time", response_model=AverageExecutionTimeResponse)
def average_execution_time(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_service_order_service(db).get_average_execution_time()


@admin_router.get("/in-progress/with-withdrawals", response_model=list[ServiceOrderResponse])
def list_os_with_withdrawals(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_execution_service(db).list_os_with_withdrawals()


@admin_router.get("/{service_order_id}", response_model=ServiceOrderResponse)
def get_service_order(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_service_order_service(db).get_by_id(service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.put("/{service_order_id}", response_model=ServiceOrderResponse)
def update_service_order(
    service_order_id: int,
    data: ServiceOrderUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_service_order_service(db).update(
            service_order_id=service_order_id,
            mechanic_name=data.mechanic_name,
            priority=data.priority,
        )
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.patch("/{service_order_id}/status-override", response_model=ServiceOrderResponse)
def override_status(
    service_order_id: int,
    data: OverrideStatusRequest,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_service_order_service(db).override_status(
            service_order_id,
            data.status,
            data.reason,
        )
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
        return compose_service_order_service(db).assign_mechanic(
            service_order_id,
            data.mechanic_name,
        )
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
        return compose_service_order_service(db).set_priority(service_order_id, data.priority)
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.post("/{service_order_id}/send-email", response_model=MessageResponse)
async def send_os_email(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        await compose_service_order_email_service(db).send_os_email(service_order_id)
        return MessageResponse(message="Email da OS enviado.")
    except DomainError as e:
        raise domain_error_handler(e)


@public_router.get("/{service_order_id}", response_model=ServiceOrderPublicResponse)
def track_service_order(
    service_order_id: int,
    document: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        return compose_service_order_service(db).get_by_customer_document(
            service_order_id,
            document,
        )
    except DomainError as e:
        raise domain_error_handler(e)
