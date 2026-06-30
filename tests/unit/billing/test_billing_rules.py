import pytest
from dataclasses import replace

from src.domain.billing.rules import calculate_invoice_amount, validate_priced_lines
from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import ValidationError
from src.domain.service_order.entity import (
    ServiceOrder,
    ServiceOrderProductLine,
    ServiceOrderServiceLine,
)


def _service_order(**overrides) -> ServiceOrder:
    base = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.FINALIZADA,
        service_lines=[
            ServiceOrderServiceLine(
                id=1,
                service_order_id=1,
                service_id=10,
                quantity=2,
                unit_price=50.0,
            )
        ],
        product_lines=[
            ServiceOrderProductLine(
                id=1,
                service_order_id=1,
                product_id=20,
                quantity=3,
                unit_price=10.0,
            )
        ],
    )
    return replace(base, **overrides)


def test_calculate_invoice_amount_sums_service_and_product_lines():
    amount = calculate_invoice_amount(_service_order())

    assert amount == 130.0


def test_validate_priced_lines_rejects_zero_service_price():
    order = _service_order(
        service_lines=[
            ServiceOrderServiceLine(
                id=1,
                service_order_id=1,
                service_id=10,
                quantity=1,
                unit_price=0.0,
            )
        ],
        product_lines=[],
    )

    with pytest.raises(ValidationError, match="precificação válida"):
        validate_priced_lines(order)


def test_validate_priced_lines_rejects_zero_product_price():
    order = _service_order(
        service_lines=[],
        product_lines=[
            ServiceOrderProductLine(
                id=1,
                service_order_id=1,
                product_id=20,
                quantity=1,
                unit_price=0.0,
            )
        ],
    )

    with pytest.raises(ValidationError, match="precificação válida"):
        validate_priced_lines(order)
