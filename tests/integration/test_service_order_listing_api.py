from datetime import datetime, timedelta

import pytest

from src.domain.enums import ServiceOrderStatus
from src.infrastructure.database import CustomerModel, ServiceOrderModel, VehicleModel

BASE_CREATED_AT = datetime(2026, 7, 1, 10, 0, 0)
LISTING_URL = "/api/v1/admin/service-orders"


def seed_service_orders(db_session, statuses: list[ServiceOrderStatus]) -> list[dict[str, object]]:
    seeded: list[dict[str, object]] = []
    for offset, status in enumerate(statuses):
        customer = CustomerModel(
            name=f"Cliente {offset}",
            email=f"cliente{offset}@test.local",
            address="Rua Um, 100",
        )
        db_session.add(customer)
        db_session.flush()
        vehicle = VehicleModel(
            customer_id=customer.id,
            plate=f"ABC{offset:04d}",
            state="SP",
            city="São Paulo",
            color="Preto",
            brand="Fiat",
            model="Uno",
            year=2020,
        )
        db_session.add(vehicle)
        db_session.flush()
        service_order = ServiceOrderModel(
            customer_id=customer.id,
            vehicle_id=vehicle.id,
            status=status,
            created_at=BASE_CREATED_AT + timedelta(hours=offset),
            updated_at=BASE_CREATED_AT + timedelta(days=1, hours=offset),
        )
        db_session.add(service_order)
        db_session.flush()
        seeded.append(
            {
                "id": service_order.id,
                "status": status,
                "customer_name": customer.name,
                "vehicle_plate": vehicle.plate,
            }
        )
    db_session.commit()
    return seeded


@pytest.fixture
def operational_and_closed_orders(db_session) -> list[dict[str, object]]:
    return seed_service_orders(
        db_session,
        [
            ServiceOrderStatus.RECEBIDA,
            ServiceOrderStatus.EM_DIAGNOSTICO,
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
            ServiceOrderStatus.AGUARDANDO_INICIO,
            ServiceOrderStatus.AGUARDANDO_COMPRA,
            ServiceOrderStatus.EM_EXECUCAO,
            ServiceOrderStatus.FINALIZADA,
            ServiceOrderStatus.ENTREGUE,
        ],
    )


def test_listing_requires_authentication(client):
    response = client.get(LISTING_URL)

    assert response.status_code == 401


def test_default_listing_excludes_closed_and_returns_joined_fields(
    client,
    auth_headers,
    operational_and_closed_orders,
):
    body = client.get(LISTING_URL, headers=auth_headers).json()

    assert {item["status"] for item in body["items"]} == {
        status.value
        for status in {
            ServiceOrderStatus.RECEBIDA,
            ServiceOrderStatus.EM_DIAGNOSTICO,
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
            ServiceOrderStatus.AGUARDANDO_INICIO,
            ServiceOrderStatus.AGUARDANDO_COMPRA,
            ServiceOrderStatus.EM_EXECUCAO,
        }
    }
    first = next(item for item in body["items"] if item["id"] == operational_and_closed_orders[0]["id"])
    assert first["customer_name"] == operational_and_closed_orders[0]["customer_name"]
    assert first["vehicle_plate"] == operational_and_closed_orders[0]["vehicle_plate"]
    assert first["updated_at"]
    assert body["total"] == 6
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 1


def test_default_ordering_uses_created_at_ascending(
    client,
    auth_headers,
    db_session,
):
    seeded = seed_service_orders(
        db_session,
        [
            ServiceOrderStatus.RECEBIDA,
            ServiceOrderStatus.AGUARDANDO_INICIO,
            ServiceOrderStatus.EM_EXECUCAO,
            ServiceOrderStatus.AGUARDANDO_INICIO,
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ],
    )

    body = client.get(LISTING_URL, headers=auth_headers).json()

    assert [item["id"] for item in body["items"]] == [item["id"] for item in seeded]


def test_explicit_status_priority_ordering_is_supported(client, auth_headers, db_session):
    seeded = seed_service_orders(
        db_session,
        [
            ServiceOrderStatus.RECEBIDA,
            ServiceOrderStatus.AGUARDANDO_INICIO,
            ServiceOrderStatus.EM_EXECUCAO,
            ServiceOrderStatus.AGUARDANDO_INICIO,
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ],
    )

    body = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"order_by": "status_priority"},
    ).json()

    assert [item["id"] for item in body["items"]] == [
        seeded[2]["id"],
        seeded[1]["id"],
        seeded[3]["id"],
        seeded[4]["id"],
        seeded[0]["id"],
    ]


def test_equal_created_at_uses_id_ascending_as_tie_breaker(client, auth_headers, db_session):
    seeded = seed_service_orders(
        db_session,
        [ServiceOrderStatus.EM_EXECUCAO, ServiceOrderStatus.EM_EXECUCAO],
    )
    same_created_at = BASE_CREATED_AT
    db_session.query(ServiceOrderModel).update({"created_at": same_created_at})
    db_session.commit()

    body = client.get(LISTING_URL, headers=auth_headers).json()

    assert [item["id"] for item in body["items"]] == [seeded[0]["id"], seeded[1]["id"]]


def test_explicit_created_at_desc_ordering_is_supported(client, auth_headers, db_session):
    seeded = seed_service_orders(
        db_session,
        [ServiceOrderStatus.RECEBIDA, ServiceOrderStatus.RECEBIDA, ServiceOrderStatus.RECEBIDA],
    )

    body = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"order_by": "created_at_desc"},
    ).json()

    assert [item["id"] for item in body["items"]] == [
        seeded[2]["id"],
        seeded[1]["id"],
        seeded[0]["id"],
    ]


def test_include_closed_returns_every_status(client, auth_headers, operational_and_closed_orders):
    body = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"include_closed": True},
    ).json()

    assert {item["status"] for item in body["items"]} == {status.value for status in ServiceOrderStatus}
    assert body["total"] == 8


def test_explicit_closed_status_is_not_hidden_by_default(client, auth_headers, operational_and_closed_orders):
    body = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"status": ServiceOrderStatus.FINALIZADA.value},
    ).json()

    assert [item["id"] for item in body["items"]] == [operational_and_closed_orders[6]["id"]]
    assert body["total"] == 1


def test_pagination_returns_metadata_and_empty_out_of_range_page(client, auth_headers, db_session):
    seeded = seed_service_orders(db_session, [ServiceOrderStatus.RECEBIDA] * 25)

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
    third_page = client.get(
        LISTING_URL,
        headers=auth_headers,
        params={"page": 3, "page_size": 20},
    ).json()

    assert [item["id"] for item in first_page["items"]] == [item["id"] for item in seeded[:20]]
    assert [item["id"] for item in second_page["items"]] == [item["id"] for item in seeded[20:]]
    assert third_page["items"] == []
    assert (first_page["total"], first_page["total_pages"]) == (25, 2)


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": 101},
        {"order_by": "created_at"},
        {"status": "not-a-status"},
        {"include_closed": "not-a-bool"},
    ],
)
def test_invalid_listing_parameters_return_422(client, auth_headers, params):
    response = client.get(LISTING_URL, headers=auth_headers, params=params)

    assert response.status_code == 422
