import pytest

from src.domain.enums import Priority, ServiceOrderStatus
from src.domain.exceptions import ValidationError
from src.domain.service_order.entity import ServiceOrder


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


def test_service_order_assigns_mechanic_without_leaving_ready_queue():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.AGUARDANDO_INICIO,
    )

    service_order.assign_mechanic("Mecânico A")

    assert service_order.mechanic_name == "Mecânico A"
    assert service_order.status == ServiceOrderStatus.AGUARDANDO_INICIO
    assert service_order.status_history[-1].transition_type == "mechanic_assignment"


def test_service_order_assigns_mechanic_while_waiting_for_purchase():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.AGUARDANDO_COMPRA,
    )

    service_order.assign_mechanic("Mecânico A")

    assert service_order.mechanic_name == "Mecânico A"
    assert service_order.status == ServiceOrderStatus.AGUARDANDO_COMPRA
