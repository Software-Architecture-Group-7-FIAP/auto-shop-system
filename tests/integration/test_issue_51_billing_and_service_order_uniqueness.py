from decimal import Decimal

import pytest

from src.domain.budget.entity import Budget
from src.domain.enums import InvoiceStatus, PaymentMethod, ServiceOrderStatus
from src.domain.exceptions import ConflictError
from src.infrastructure.budget_approval import SqlAlchemyApprovedBudgetServiceOrderCreator
from src.infrastructure.database import (
    BudgetModel,
    CustomerModel,
    InvoiceModel,
    ServiceOrderModel,
    VehicleModel,
)


def _seed_invoice(db_session, status=ServiceOrderStatus.FINALIZADA):
    db_session.add(CustomerModel(name="Cliente", email="cliente@test.local", address="Rua A"))
    db_session.flush()
    db_session.add(
        VehicleModel(
            customer_id=1,
            plate="ABC1D23",
            state="SP",
            city="São Paulo",
            color="Preto",
            brand="Toyota",
            model="Corolla",
            year=2022,
        )
    )
    db_session.flush()
    order = ServiceOrderModel(
        customer_id=1,
        vehicle_id=1,
        status=status,
        total_price=100.0,
    )
    db_session.add(order)
    db_session.flush()
    invoice = InvoiceModel(service_order_id=order.id, amount=Decimal("100.00"))
    db_session.add(invoice)
    db_session.commit()
    return order.id, invoice.id


def test_partial_payment_is_idempotent_and_keeps_order_undelivered(
    client, auth_headers, db_session
):
    order_id, invoice_id = _seed_invoice(db_session)

    response = client.post(
        f"/api/v1/admin/invoices/{invoice_id}/payments",
        headers={**auth_headers, "Idempotency-Key": "payment-1"},
        json={"amount": "40.00", "method": PaymentMethod.PIX.value},
    )
    replay = client.post(
        f"/api/v1/admin/invoices/{invoice_id}/payments",
        headers={**auth_headers, "Idempotency-Key": "payment-1"},
        json={"amount": "40.00", "method": PaymentMethod.PIX.value},
    )

    assert response.status_code == 200
    assert replay.status_code == 200
    assert response.json()["status"] == InvoiceStatus.PARTIALLY_PAID.value
    assert response.json()["balance"] == "60.00"
    assert len(replay.json()["payments"]) == 1
    assert db_session.get(ServiceOrderModel, order_id).status == ServiceOrderStatus.FINALIZADA


def test_payment_requires_an_explicit_idempotency_key(client, auth_headers, db_session):
    _, invoice_id = _seed_invoice(db_session)

    response = client.post(
        f"/api/v1/admin/invoices/{invoice_id}/payments",
        headers=auth_headers,
        json={"amount": "40.00", "method": PaymentMethod.PIX.value},
    )

    assert response.status_code == 422


def test_payment_rejects_a_blank_idempotency_key(client, auth_headers, db_session):
    _, invoice_id = _seed_invoice(db_session)

    response = client.post(
        f"/api/v1/admin/invoices/{invoice_id}/payments",
        headers={**auth_headers, "Idempotency-Key": "   "},
        json={"amount": "40.00", "method": PaymentMethod.PIX.value},
    )

    assert response.status_code == 422


def test_exact_payment_marks_invoice_paid_and_delivers_finalized_order(
    client, auth_headers, db_session
):
    order_id, invoice_id = _seed_invoice(db_session)

    response = client.post(
        f"/api/v1/admin/invoices/{invoice_id}/payments",
        headers={**auth_headers, "Idempotency-Key": "payment-exact"},
        json={"amount": "100.00", "method": PaymentMethod.TRANSFERENCIA.value},
    )

    assert response.status_code == 200
    assert response.json()["status"] == InvoiceStatus.PAID.value
    assert db_session.get(ServiceOrderModel, order_id).status == ServiceOrderStatus.ENTREGUE


def test_active_service_order_conflicts_but_delivered_history_does_not(
    db_session,
):
    db_session.add(CustomerModel(name="Cliente", email="cliente@test.local", address="Rua A"))
    db_session.flush()
    db_session.add(
        VehicleModel(
            customer_id=1,
            plate="ABC1D23",
            state="SP",
            city="São Paulo",
            color="Preto",
            brand="Toyota",
            model="Corolla",
            year=2022,
        )
    )
    db_session.add(BudgetModel(customer_id=1, vehicle_id=1))
    db_session.add(
        ServiceOrderModel(
            budget_id=1,
            customer_id=1,
            vehicle_id=1,
            status=ServiceOrderStatus.RECEBIDA,
        )
    )
    db_session.commit()

    creator = SqlAlchemyApprovedBudgetServiceOrderCreator(db_session)
    with pytest.raises(ConflictError, match="OS ativa"):
        creator.create_from_budget(Budget(id=2, customer_id=1, vehicle_id=1))

    db_session.query(ServiceOrderModel).filter(ServiceOrderModel.budget_id == 1).update(
        {ServiceOrderModel.status: ServiceOrderStatus.ENTREGUE}
    )
    db_session.add(BudgetModel(id=2, customer_id=1, vehicle_id=1))
    db_session.commit()

    created = creator.create_from_budget(Budget(id=2, customer_id=1, vehicle_id=1))

    assert created.id != 1
    assert (
        db_session.get(ServiceOrderModel, created.id).status
        == ServiceOrderStatus.AGUARDANDO_INICIO
    )
