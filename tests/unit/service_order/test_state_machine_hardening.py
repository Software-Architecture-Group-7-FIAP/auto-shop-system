from datetime import datetime

import pytest

from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import ValidationError
from src.domain.service_order.entity import ServiceOrder


def make_order(**overrides: object) -> ServiceOrder:
    values: dict[str, object] = {
        "id": 1,
        "budget_id": 2,
        "customer_id": 3,
        "vehicle_id": 4,
    }
    values.update(overrides)
    return ServiceOrder(**values)


def test_canonical_workflow_requires_each_transition_in_order() -> None:
    order = make_order()

    order.assign_mechanic(" Ana ")
    order.submit_for_approval()
    order.approve_current_budget()
    order.start_execution(datetime(2026, 1, 1, 8, 0, 0))
    order.finish_execution(datetime(2026, 1, 1, 12, 0, 0))
    order.mark_delivered()

    assert order.status == ServiceOrderStatus.ENTREGUE
    assert [event.to_status for event in order.status_history] == [
        ServiceOrderStatus.EM_DIAGNOSTICO,
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.AGUARDANDO_INICIO,
        ServiceOrderStatus.EM_EXECUCAO,
        ServiceOrderStatus.FINALIZADA,
        ServiceOrderStatus.ENTREGUE,
    ]


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ServiceOrderStatus.RECEBIDA, ServiceOrderStatus.EM_EXECUCAO),
        (ServiceOrderStatus.EM_DIAGNOSTICO, ServiceOrderStatus.AGUARDANDO_INICIO),
        (ServiceOrderStatus.AGUARDANDO_INICIO, ServiceOrderStatus.FINALIZADA),
        (ServiceOrderStatus.FINALIZADA, ServiceOrderStatus.EM_EXECUCAO),
        (ServiceOrderStatus.ENTREGUE, ServiceOrderStatus.RECEBIDA),
    ],
)
def test_invalid_workflow_transition_is_rejected(
    from_status: ServiceOrderStatus,
    to_status: ServiceOrderStatus,
) -> None:
    order = make_order(status=from_status)

    with pytest.raises(ValidationError, match="não permitida"):
        order.transition_to(to_status)


def test_first_mechanic_assignment_transitions_only_received_order() -> None:
    order = make_order(status=ServiceOrderStatus.EM_DIAGNOSTICO)

    with pytest.raises(ValidationError, match="primeira atribuição"):
        order.assign_mechanic("Ana")


def test_mechanic_reassignment_requires_reason_and_does_not_regress_status() -> None:
    order = make_order()
    order.assign_mechanic("Ana")
    order.submit_for_approval()

    with pytest.raises(ValidationError, match="Motivo da troca"):
        order.assign_mechanic("Bruno")

    order.assign_mechanic(" Bruno ", "cobertura de férias")
    assert order.mechanic_name == "Bruno"
    assert order.status == ServiceOrderStatus.AGUARDANDO_APROVACAO
    assert order.status_history[-1].transition_type == "mechanic_reassignment"


def test_break_glass_override_cannot_touch_execution_states() -> None:
    order = make_order(status=ServiceOrderStatus.AGUARDANDO_APROVACAO)

    with pytest.raises(ValidationError, match="estados iniciais"):
        order.override_status(ServiceOrderStatus.EM_EXECUCAO, "correção")


def test_break_glass_override_records_reason_and_actor() -> None:
    order = make_order(status=ServiceOrderStatus.AGUARDANDO_APROVACAO)

    order.override_status(
        ServiceOrderStatus.EM_DIAGNOSTICO,
        "revisão solicitada pelo cliente",
        actor_id=10,
        request_id="req-1",
    )

    event = order.status_history[-1]
    assert (event.from_status, event.to_status) == (
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.EM_DIAGNOSTICO,
    )
    assert event.reason == "revisão solicitada pelo cliente"
    assert event.actor_id == 10
    assert event.request_id == "req-1"
