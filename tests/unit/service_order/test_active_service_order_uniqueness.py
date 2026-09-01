from src.domain.enums import ServiceOrderStatus


def test_only_delivered_service_orders_are_terminal_for_vehicle_uniqueness():
    active_statuses = {
        ServiceOrderStatus.RECEBIDA,
        ServiceOrderStatus.EM_DIAGNOSTICO,
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.AGUARDANDO_INICIO,
        ServiceOrderStatus.EM_EXECUCAO,
        ServiceOrderStatus.FINALIZADA,
    }

    assert ServiceOrderStatus.ENTREGUE not in active_statuses
    assert set(ServiceOrderStatus) - {ServiceOrderStatus.ENTREGUE} == active_statuses
