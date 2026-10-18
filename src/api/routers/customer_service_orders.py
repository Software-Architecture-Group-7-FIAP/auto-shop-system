import logging

from fastapi import APIRouter, Depends, Path, Request, Response
from sqlalchemy.orm import Session

from src.api.composition.service_orders import compose_service_order_service
from src.api.dependencies import get_current_customer
from src.api.request_context import request_correlation_id
from src.api.schemas import (
    CustomerServiceOrderProductLineResponse,
    CustomerServiceOrderResponse,
    CustomerServiceOrderServiceLineResponse,
)
from src.domain.auth.principal import CustomerPrincipal
from src.domain.exceptions import NotFoundError
from src.infrastructure.database import get_db


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/customer/service-orders", tags=["Customer Service Orders"])


@router.get("/{service_order_id}", response_model=CustomerServiceOrderResponse)
def get_customer_service_order(
    request: Request,
    response: Response,
    service_order_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    principal: CustomerPrincipal = Depends(get_current_customer),
) -> CustomerServiceOrderResponse:
    correlation_id = request_correlation_id(request)
    try:
        service_order = compose_service_order_service(db).get_by_id_for_customer(
            service_order_id,
            principal.customer_id,
        )
    except NotFoundError:
        logger.warning(
            "customer_service_order_access_denied request_id=%s service_order_id=%s",
            correlation_id,
            service_order_id,
        )
        raise

    response.headers["Cache-Control"] = "no-store"
    return CustomerServiceOrderResponse(
        id=service_order.id,
        status=service_order.status,
        total_price=service_order.total_price,
        created_at=service_order.created_at,
        started_at=service_order.started_at,
        finished_at=service_order.finished_at,
        service_lines=[
            CustomerServiceOrderServiceLineResponse(
                service_id=line.service_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
            for line in service_order.service_lines
        ],
        product_lines=[
            CustomerServiceOrderProductLineResponse(
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
            for line in service_order.product_lines
        ],
    )
