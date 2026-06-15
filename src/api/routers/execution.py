from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import MessageResponse, ServiceOrderResponse, StockWithdrawalCreate, StockWithdrawalResponse
from src.application.services.execution_service import ExecutionService
from src.domain.exceptions import DomainError
from src.infrastructure.database import UserModel, get_db

execution_router = APIRouter(prefix="/admin/service-orders", tags=["Execution"])
withdrawals_router = APIRouter(prefix="/admin/stock-withdrawals", tags=["Execution"])


@execution_router.post("/{service_order_id}/enqueue", response_model=ServiceOrderResponse)
def enqueue_service_order(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ExecutionService(db).enqueue(service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@execution_router.patch("/{service_order_id}/start", response_model=ServiceOrderResponse)
def start_service(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ExecutionService(db).start_service(service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@execution_router.patch("/{service_order_id}/finish", response_model=ServiceOrderResponse)
def finish_service(
    service_order_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ExecutionService(db).finish_service(service_order_id)
    except DomainError as e:
        raise domain_error_handler(e)


@withdrawals_router.post("", response_model=StockWithdrawalResponse, status_code=201)
async def request_stock_withdrawal(
    data: StockWithdrawalCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return await ExecutionService(db).request_stock_withdrawal(
            data.service_order_id, data.product_id, data.quantity
        )
    except DomainError as e:
        raise domain_error_handler(e)


@withdrawals_router.get("/pending", response_model=list[StockWithdrawalResponse])
def list_pending_withdrawals(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return ExecutionService(db).list_pending_withdrawals()
