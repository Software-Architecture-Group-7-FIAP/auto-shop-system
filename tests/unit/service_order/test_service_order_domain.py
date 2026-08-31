import pytest

from src.domain.enums import Priority, ServiceOrderStatus
from src.domain.exceptions import ValidationError
from src.domain.service_order.entity import (
    ServiceOrder,
    ServiceOrderProductLine,
)


def test_service_order_assign_mechanic_sets_status():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
    )

    service_order.assign_mechanic("Mecânico A")

    assert service_order.mechanic_name == "Mecânico A"
    assert service_order.status == ServiceOrderStatus.EM_DIAGNOSTICO


def test_service_order_assign_mechanic_rejects_blank_name():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
    )

    with pytest.raises(ValidationError, match="Nome do mecânico é obrigatório"):
        service_order.assign_mechanic("   ")


def test_service_order_sets_priority():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
    )

    service_order.set_priority(Priority.HIGH)

    assert service_order.priority == Priority.HIGH


def test_service_order_assign_mechanic_trims_name():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
    )

    service_order.assign_mechanic(" Mecânico A ")

    assert service_order.mechanic_name == "Mecânico A"
    assert service_order.status == ServiceOrderStatus.EM_DIAGNOSTICO


def test_service_order_open_accepts_product_only_scope():
    service_order = ServiceOrder.open(
        customer_id=1,
        vehicle_id=2,
        service_lines=[],
        product_lines=[
            ServiceOrderProductLine(
                id=None,
                service_order_id=None,
                product_id=3,
                quantity=2,
                unit_price=25.0,
            )
        ],
    )

    assert service_order.status == ServiceOrderStatus.RECEBIDA
    assert service_order.total_price == 50.0


def test_service_order_open_rejects_empty_scope():
    with pytest.raises(ValidationError, match="serviço ou produto"):
        ServiceOrder.open(1, 2, [], [])
