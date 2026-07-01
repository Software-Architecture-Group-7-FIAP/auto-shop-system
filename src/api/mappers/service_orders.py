from src.api.schemas import (
    ServiceOrderProductLineResponse,
    ServiceOrderWithWithdrawalsResponse,
    StockWithdrawalResponse,
)
from src.application.services.execution_service import ServiceOrderWithdrawalDetail


def service_order_with_withdrawals_to_response(
    detail: ServiceOrderWithdrawalDetail,
) -> ServiceOrderWithWithdrawalsResponse:
    service_order = detail.service_order
    return ServiceOrderWithWithdrawalsResponse(
        id=service_order.id,
        status=service_order.status,
        priority=service_order.priority,
        mechanic_name=service_order.mechanic_name,
        total_price=service_order.total_price,
        started_at=service_order.started_at,
        created_at=service_order.created_at,
        product_lines=[
            ServiceOrderProductLineResponse(
                id=line.id,
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
            for line in service_order.product_lines
        ],
        withdrawals=[
            StockWithdrawalResponse(
                id=withdrawal.id,
                service_order_id=withdrawal.service_order_id,
                product_id=withdrawal.product_id,
                quantity=withdrawal.quantity,
                status=withdrawal.status,
                requested_at=withdrawal.requested_at,
                fulfilled_at=withdrawal.fulfilled_at,
            )
            for withdrawal in detail.withdrawals
        ],
    )
