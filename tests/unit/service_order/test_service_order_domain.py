from src.domain.enums import Priority, ServiceOrderStatus
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


def test_service_order_sets_priority():
    service_order = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
    )

    service_order.set_priority(Priority.HIGH)

    assert service_order.priority == Priority.HIGH
