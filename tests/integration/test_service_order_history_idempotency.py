from src.domain.enums import ServiceOrderStatus
from src.infrastructure.database import (
    CustomerModel,
    ServiceOrderModel,
    VehicleModel,
)
from src.infrastructure.persistence.service_order_repository import (
    SqlAlchemyServiceOrderRepository,
)


def test_repeated_request_id_does_not_duplicate_service_order_history(
    db_session,
):
    customer = CustomerModel(
        name="Cliente histórico",
        email="history@test.com",
        address="Rua 1",
    )
    db_session.add(customer)
    db_session.flush()
    vehicle = VehicleModel(
        customer_id=customer.id,
        plate="HIS1A23",
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
        status=ServiceOrderStatus.RECEBIDA,
    )
    db_session.add(model)
    db_session.commit()

    repository = SqlAlchemyServiceOrderRepository(db_session)
    order = repository.get_by_id(model.id)
    assert order is not None
    order.assign_mechanic("Ana", request_id="request-1")
    repository.save(order)
    db_session.commit()

    order = repository.get_by_id(model.id)
    assert order is not None
    order.assign_mechanic("Bruno", "cobertura", request_id="request-1")
    repository.save(order)
    db_session.commit()

    history = repository.get_by_id(model.id).status_history
    assert len(history) == 1
    assert history[0].request_id == "request-1"
