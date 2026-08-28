from datetime import datetime, timedelta, timezone

from src.domain.enums import ServiceOrderStatus
from src.infrastructure.database import (
    CustomerModel,
    ServiceOrderModel,
    VehicleModel,
)
from src.infrastructure.persistence.service_order_repository import (
    SqlAlchemyServiceOrderRepository,
)


def _service_order(db_session, *, fingerprint: str, expires_at: datetime):
    customer = CustomerModel(
        name="Cliente tracking",
        email="tracking@test.com",
        address="Rua 1",
    )
    db_session.add(customer)
    db_session.flush()
    vehicle = VehicleModel(
        customer_id=customer.id,
        plate="TRK1A23",
        state="SP",
        city="São Paulo",
        color="Prata",
        brand="Fiat",
        model="Uno",
        year=2020,
    )
    db_session.add(vehicle)
    db_session.flush()
    model = ServiceOrderModel(
        customer_id=customer.id,
        vehicle_id=vehicle.id,
        status=ServiceOrderStatus.EM_DIAGNOSTICO,
        tracking_token_hash=fingerprint,
        tracking_token_expires_at=expires_at,
    )
    db_session.add(model)
    db_session.commit()
    return model


def test_tracking_token_expiry_is_enforced_before_delivery(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    model = _service_order(
        db_session,
        fingerprint="expired-fingerprint",
        expires_at=now - timedelta(seconds=1),
    )

    repository = SqlAlchemyServiceOrderRepository(db_session)

    assert repository.get_by_tracking_token_fingerprint("expired-fingerprint") is None

    model.tracking_token_expires_at = now + timedelta(days=1)
    db_session.commit()
    assert repository.get_by_tracking_token_fingerprint("expired-fingerprint") is not None


def test_resending_tracking_token_replaces_the_previous_token_and_expiry(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    model = _service_order(
        db_session,
        fingerprint="old-fingerprint",
        expires_at=now + timedelta(days=1),
    )
    repository = SqlAlchemyServiceOrderRepository(db_session)

    repository.set_tracking_token_fingerprint(
        model.id,
        "new-fingerprint",
        now + timedelta(days=7),
    )
    db_session.commit()

    assert repository.get_by_tracking_token_fingerprint("old-fingerprint") is None
    assert repository.get_by_tracking_token_fingerprint("new-fingerprint") is not None


def test_saving_a_delivered_order_does_not_extend_tracking_expiry(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    model = _service_order(
        db_session,
        fingerprint="fixed-expiry-fingerprint",
        expires_at=now - timedelta(seconds=1),
    )
    repository = SqlAlchemyServiceOrderRepository(db_session)
    order = repository.get_by_id(model.id)
    assert order is not None

    repository.save(order)
    db_session.commit()
    db_session.refresh(model)

    assert model.tracking_token_expires_at < now
