from datetime import datetime, timedelta

import pytest

from src.domain.enums import ServiceOrderStatus
from src.infrastructure.database import CustomerModel, ServiceOrderModel, VehicleModel

BASE_CREATED_AT = datetime(2026, 7, 1, 10, 0, 0)
LISTING_URL = "/api/v1/admin/service-orders"


def seed_service_orders(
    db_session,
    statuses: list[ServiceOrderStatus],
) -> list[int]:
    customer = CustomerModel(
        name="Oficina Cliente",
        email="cliente@test.local",
        address="Rua Um, 100",
    )
    db_session.add(customer)
    db_session.flush()

    vehicle = VehicleModel(
        customer_id=customer.id,
        plate="ABC1234",
        state="SP",
        city="São Paulo",
        color="Preto",
        brand="Fiat",
        model="Uno",
        year=2020,
    )
    db_session.add(vehicle)
    db_session.flush()

    service_orders = [
        ServiceOrderModel(
            customer_id=customer.id,
            vehicle_id=vehicle.id,
            status=status,
            created_at=BASE_CREATED_AT + timedelta(hours=offset),
        )
        for offset, status in enumerate(statuses)
    ]
    db_session.add_all(service_orders)
    db_session.commit()
    return [service_order.id for service_order in service_orders]


@pytest.fixture
def operational_and_closed_orders(db_session) -> dict[ServiceOrderStatus, int]:
    statuses = [
        ServiceOrderStatus.RECEBIDA,
        ServiceOrderStatus.EM_DIAGNOSTICO,
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.EM_EXECUCAO,
        ServiceOrderStatus.FINALIZADA,
        ServiceOrderStatus.ENTREGUE,
    ]
    ids = seed_service_orders(db_session, statuses)
    return dict(zip(statuses, ids))


def test_listing_requires_authentication(client):
    response = client.get(LISTING_URL)

    assert response.status_code == 401


def test_operational_listing_excludes_finished_and_delivered(
    client,
    auth_headers,
    operational_and_closed_orders,
):
    body = client.get(LISTING_URL, headers=auth_headers).json()

    returned_statuses = {item["status"] for item in body["items"]}
    assert returned_statuses == {
        ServiceOrderStatus.RECEBIDA,
        ServiceOrderStatus.EM_DIAGNOSTICO,
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.EM_EXECUCAO,
    }
    assert body["total"] == 4


def test_default_ordering_ranks_status_then_oldest_first(client, auth_headers, db_session):
    ids = seed_service_orders(
        db_session,
        [
            ServiceOrderStatus.EM_EXECUCAO,
            ServiceOrderStatus.RECEBIDA,
            ServiceOrderStatus.EM_EXECUCAO,
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ],
    )
    oldest_execution, received, newest_execution, awaiting = ids

    body = client.get(LISTING_URL, headers=auth_headers).json()

    assert [item["id"] for item in body["items"]] == [
        oldest_execution,
        newest_execution,
        awaiting,
        received,
    ]


def test_created_at_ordering_can_be_requested_explicitly(client, auth_headers, db_session):
    ids = seed_service_orders(
        db_session,
        [
            ServiceOrderStatus.EM_EXECUCAO,
            ServiceOrderStatus.RECEBIDA,
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ],
    )

    body = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"order_by": "created_at_asc"},
    ).json()

    assert [item["id"] for item in body["items"]] == ids
    assert [item["created_at"] for item in body["items"]] == sorted(
        item["created_at"] for item in body["items"]
    )


def test_include_closed_returns_every_status(
    client,
    auth_headers,
    operational_and_closed_orders,
):
    body = client.get(LISTING_URL, headers=auth_headers, params={"include_closed": True}).json()

    returned_statuses = {item["status"] for item in body["items"]}
    assert returned_statuses == set(ServiceOrderStatus)
    assert body["total"] == 6


def test_pagination_limits_the_page_and_reports_metadata(client, auth_headers, db_session):
    ids = seed_service_orders(db_session, [ServiceOrderStatus.RECEBIDA] * 25)

    first_page = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"page": 1, "page_size": 20},
    ).json()
    second_page = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"page": 2, "page_size": 20},
    ).json()

    assert [item["id"] for item in first_page["items"]] == ids[:20]
    assert [item["id"] for item in second_page["items"]] == ids[20:]
    assert (
        first_page["total"],
        first_page["page"],
        first_page["page_size"],
        first_page["total_pages"],
    ) == (25, 1, 20, 2)


def test_page_size_is_capped(client, auth_headers):
    response = client.get(LISTING_URL, headers=auth_headers, params={"page_size": 101})

    assert response.status_code == 422


def test_status_filter_returns_only_the_requested_status(
    client,
    auth_headers,
    operational_and_closed_orders,
):
    body = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"status": ServiceOrderStatus.EM_EXECUCAO.value},
    ).json()

    assert [item["id"] for item in body["items"]] == [
        operational_and_closed_orders[ServiceOrderStatus.EM_EXECUCAO]
    ]
    assert body["total"] == 1


def test_closed_status_filter_needs_include_closed(
    client,
    auth_headers,
    operational_and_closed_orders,
):
    without_closed = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"status": ServiceOrderStatus.FINALIZADA.value},
    ).json()
    with_closed = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"status": ServiceOrderStatus.FINALIZADA.value, "include_closed": True},
    ).json()

    assert without_closed["items"] == []
    assert without_closed["total"] == 0
    assert [item["id"] for item in with_closed["items"]] == [
        operational_and_closed_orders[ServiceOrderStatus.FINALIZADA]
    ]
