from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.domain.budget.entity import Budget, ProductAvailability
from src.domain.enums import BudgetStatus
from src.domain.exceptions import ValidationError


def test_budget_create_sets_default_status_and_totals():
    budget = Budget.create(customer_id=1, vehicle_id=2)

    assert budget.customer_id == 1
    assert budget.vehicle_id == 2
    assert budget.status == BudgetStatus.DRAFT
    assert budget.total_price == 0.0


def test_budget_add_lines_and_recalculate_totals():
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    budget = Budget(id=1, customer_id=1, vehicle_id=2)
    service_line = budget.add_service_line(service_id=10, quantity=2, base_price=100.0, resolved_requirements=[{"product_id": 20, "quantity": 3, "unit_price": 15.0}])
    product_line = budget.add_product_line(
        product_id=20,
        quantity=3,
        unit_price=15.0,
        from_service=False,
    )
    budget.service_lines.append(service_line)
    budget.product_lines.append(product_line)

    budget.recalculate_estimated_delivery(service_hours={10: 1.5}, now=now)
    budget.recalculate_total_price()
    
    assert budget.total_price == 245.0
    assert budget.estimated_delivery == now + timedelta(hours=3)


def test_budget_recalculate_uses_minimum_one_hour_delivery():
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    budget = Budget(id=1, customer_id=1, vehicle_id=2)

    budget.recalculate_estimated_delivery(service_hours={}, now=now)

    assert budget.estimated_delivery == now + timedelta(hours=1)


def test_budget_rejects_non_positive_line_quantity():
    budget = Budget(id=1, customer_id=1, vehicle_id=2)

    with pytest.raises(ValidationError):
        budget.add_service_line(service_id=10, quantity=0, base_price=100.0, resolved_requirements=[{"product_id": 20, "quantity": 3, "unit_price": 15.0}])


def test_product_availability_serializes_to_api_shape():
    availability = ProductAvailability(
        product_id=1,
        product_name="Óleo",
        required=2,
        available=5,
        sufficient=True,
    )

    assert availability.as_dict() == {
        "product_id": 1,
        "product_name": "Óleo",
        "required": 2,
        "available": 5,
        "sufficient": True,
    }
