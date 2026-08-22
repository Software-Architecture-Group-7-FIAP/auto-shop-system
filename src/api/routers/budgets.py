from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.api.composition.budget_approval import compose_budget_approval_service
from src.api.composition.budgets import compose_budget_service
from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import (
    AvailabilityItem,
    BudgetCreate,
    BudgetDecisionRequest,
    BudgetDecisionResponse,
    BudgetProductLineCreate,
    BudgetProductLineUpdate,
    BudgetProductLineResponse,
    BudgetResponse,
    BudgetServiceLineCreate,
    BudgetServiceLineUpdate,
    BudgetServiceLineResponse,
    MessageResponse,
)
from src.domain.exceptions import DomainError
from src.infrastructure.database import UserModel, get_db

admin_router = APIRouter(prefix="/admin/budgets", tags=["Budgets"])
public_router = APIRouter(prefix="/public/budgets", tags=["Public Budgets"])

@admin_router.post("", response_model=BudgetResponse, status_code=201)
def create_budget(
    data: BudgetCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_budget_service(db).create(data.customer_id, data.vehicle_id)
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.get("", response_model=list[BudgetResponse])
def list_budgets(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return compose_budget_service(db).list_all()


@admin_router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_budget_service(db).get_by_id(budget_id)
    except DomainError as e:
        raise domain_error_handler(e)

# Service Lines Management
@admin_router.post("/{budget_id}/service-lines", status_code=201)
def add_service_line(
    budget_id: int,
    data: BudgetServiceLineCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        line = compose_budget_service(db).add_service_line(
            budget_id,
            data.service_id,
            data.quantity,
        )
        return {
            "id": line.id,
            "budget_id": line.budget_id,
            "service_id": line.service_id,
            "quantity": line.quantity,
        }
    except DomainError as e:
        raise domain_error_handler(e)

@admin_router.get("/{budget_id}/service-lines", response_model=list[BudgetServiceLineResponse])
def list_service_lines(
    budget_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user)):
    try:
        return compose_budget_service(db).get_all_service_lines(budget_id)
    except DomainError as e:
        raise domain_error_handler(e)

@admin_router.put("/{budget_id}/service-lines/{line_id}", response_model=BudgetServiceLineResponse)
def update_service_line(
    budget_id: int,
    line_id: int,
    data: BudgetServiceLineUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_budget_service(db).update_service_line(
            budget_id,
            line_id,
            data.quantity,
        )
    except DomainError as e:
        raise domain_error_handler(e)

@admin_router.delete("/{budget_id}/service-lines/{line_id}", status_code=204)
def remove_service_line(
    budget_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        compose_budget_service(db).remove_service_line(budget_id, line_id)
    except DomainError as e:
        raise domain_error_handler(e)

# Product Lines
@admin_router.post("/{budget_id}/product-lines", status_code=201)
def add_product_line(
    budget_id: int,
    data: BudgetProductLineCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        line = compose_budget_service(db).add_product_line(
            budget_id,
            data.product_id,
            data.quantity,
        )
        return {
            "id": line.id,
            "budget_id": line.budget_id,
            "product_id": line.product_id,
            "quantity": line.quantity,
        }
    except DomainError as e:
        raise domain_error_handler(e)

@admin_router.get("/{budget_id}/product-lines", response_model=list[BudgetProductLineResponse])
def list_product_lines(
    budget_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user)):
    try:
        return compose_budget_service(db).get_all_product_lines(budget_id)
    except DomainError as e:
        raise domain_error_handler(e)

@admin_router.put("/{budget_id}/product-lines/{line_id}", response_model=BudgetProductLineResponse)
def update_product_line(
    budget_id: int,
    line_id: int,
    data: BudgetProductLineUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_budget_service(db).update_product_line(
            budget_id,
            line_id,
            data.quantity,
        )
    except DomainError as e:
        raise domain_error_handler(e)

@admin_router.delete("/{budget_id}/product-lines/{line_id}", status_code=204)
def remove_product_line(
    budget_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        compose_budget_service(db).remove_product_line(budget_id, line_id)
    except DomainError as e:
        raise domain_error_handler(e)

@admin_router.get("/{budget_id}/availability", response_model=list[AvailabilityItem])
def check_availability(
    budget_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_budget_service(db).check_availability(budget_id)
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.get("/{budget_id}/estimated-delivery")
def get_estimated_delivery(
    budget_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        dt = compose_budget_service(db).get_estimated_delivery(budget_id)
        return {"estimated_delivery": dt}
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.post("/{budget_id}/send-email", response_model=BudgetResponse)
async def send_budget_email(
    budget_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return await compose_budget_approval_service(db).send_budget_email(
            budget_id,
            actor_id=current_user.id,
            request_id=request.headers.get("x-request-id") or str(uuid4()),
        )
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.patch("/{budget_id}/approve", response_model=MessageResponse)
def approve_budget_admin(
    budget_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        service_order = compose_budget_approval_service(db).approve_budget_by_id(
            budget_id,
            actor_id=current_user.id,
            request_id=request.headers.get("x-request-id") or str(uuid4()),
        )
        return MessageResponse(message=f"Orçamento aprovado. OS #{service_order.id} criada.")
    except DomainError as e:
        raise domain_error_handler(e)


@public_router.post("/decisions", response_model=BudgetDecisionResponse)
def decide_budget(
    data: BudgetDecisionRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = compose_budget_approval_service(db).decide_budget(
            data.token,
            data.decision,
            request_id=request.headers.get("x-request-id") or str(uuid4()),
        )
        if data.decision == "approve":
            message = (
                f"Orçamento aprovado. OS #{result.service_order.id} criada."
                if result.service_order
                else "Orçamento já aprovado."
            )
        else:
            message = "Orçamento já recusado." if result.already_processed else "Orçamento recusado."
        return BudgetDecisionResponse(
            message=message,
            status=result.status,
            already_processed=result.already_processed,
            service_order_id=result.service_order.id if result.service_order else None,
        )
    except DomainError as e:
        raise domain_error_handler(e)


@admin_router.post("/{budget_id}/revisions", response_model=BudgetResponse, status_code=201)
def create_budget_revision(
    budget_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return compose_budget_service(db).create_revision(budget_id)
    except DomainError as e:
        raise domain_error_handler(e)
