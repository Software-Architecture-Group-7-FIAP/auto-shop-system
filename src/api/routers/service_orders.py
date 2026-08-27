from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.api.composition.service_orders import (
    compose_service_order_email_service,
    compose_service_order_service,
)
from src.api.composition.execution import compose_execution_service
from src.api.dependencies import domain_error_handler, get_current_user, require_admin
from src.api.rate_limit import enforce_public_rate_limit
from src.api.mappers.service_orders import service_order_with_withdrawals_to_response
from src.api.schemas import (
    AssignMechanicRequest,
    AverageExecutionTimeResponse,
    MessageResponse,
    OverrideStatusRequest,
    ServiceOrderPublicResponse,
    ServiceOrderTrackingRequest,
    ServiceOrderResponse,
    ServiceOrderUpdate,
    ServiceOrderWithWithdrawalsResponse,
    SetPriorityRequest,
)
from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import DomainError
from src.infrastructure.auth.service_order_tracking import HmacServiceOrderTrackingTokenService
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


@admin_router.get(
    "/in-progress/with-withdrawals",
    response_model=list[ServiceOrderWithWithdrawalsResponse],
)
def list_os_with_withdrawals(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    details = compose_execution_service(db).list_os_with_withdrawal_details()
    return [service_order_with_withdrawals_to_response(detail) for detail in details]


@admin_router.get("/queue", response_model=list[ServiceOrderResponse])
def list_execution_queue(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_execution_service(db).list_execution_queue()


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
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return compose_service_order_service(db).update(
            service_order_id=service_order_id,
            mechanic_name=data.mechanic_name,
            priority=data.priority,
            mechanic_reason=data.reason,
            actor_id=current_user.id,
            request_id=request.headers.get("x-request-id") or str(uuid4()),
        )
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.patch("/{service_order_id}/status-override", response_model=ServiceOrderResponse)
def override_status(
    service_order_id: int,
    data: OverrideStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    try:
        return compose_service_order_service(db).override_status(
            service_order_id,
            data.status,
            data.reason,
            actor_role=current_user.role,
            actor_id=current_user.id,
            request_id=request.headers.get("x-request-id") or str(uuid4()),
        )
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.patch("/{service_order_id}/assign-mechanic", response_model=ServiceOrderResponse)
def assign_mechanic(
    service_order_id: int,
    data: AssignMechanicRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return compose_service_order_service(db).assign_mechanic(
            service_order_id,
            data.mechanic_name,
            data.reason,
            actor_id=current_user.id,
            request_id=request.headers.get("x-request-id") or str(uuid4()),
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


@public_router.post("/track", response_model=ServiceOrderPublicResponse)
def track_service_order(
    data: ServiceOrderTrackingRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    enforce_public_rate_limit(
        request,
        HmacServiceOrderTrackingTokenService().fingerprint(data.token),
        "service_order_tracking",
    )
    try:
        return compose_service_order_service(db).get_by_tracking_token(data.token)
    except DomainError as e:
        raise domain_error_handler(e)
