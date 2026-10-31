from src.domain.enums import ServiceOrderStatus
from src.domain.service_order.entity import ACTIVE_SERVICE_ORDER_STATUSES


def test_only_delivered_service_orders_are_terminal_for_vehicle_uniqueness():
    active_statuses = {
        ServiceOrderStatus.RECEBIDA,
        ServiceOrderStatus.EM_DIAGNOSTICO,
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.AGUARDANDO_INICIO,
        ServiceOrderStatus.AGUARDANDO_COMPRA,
        ServiceOrderStatus.EM_EXECUCAO,
        ServiceOrderStatus.FINALIZADA,
    }

    assert ServiceOrderStatus.ENTREGUE not in active_statuses
    assert active_statuses == ACTIVE_SERVICE_ORDER_STATUSES
