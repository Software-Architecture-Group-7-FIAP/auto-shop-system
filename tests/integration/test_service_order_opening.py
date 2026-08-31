from sqlalchemy import select

from src.infrastructure.database import (
    ReservationModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
)


def _customer_and_vehicle(client, auth_headers, *, suffix: str):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json={
            "name": f"Cliente {suffix}",
            "document": "529.982.247-25",
            "email": f"cliente-{suffix}@test.com",
            "address": "Rua A, 100",
        },
    )
    assert customer.status_code == 201
    customer_data = customer.json()

    vehicle = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json={
            "customer_id": customer_data["id"],
            "plate": "ABC1D23",
            "state": "SP",
            "city": "São Paulo",
            "color": "Prata",
            "brand": "VW",
            "model": "Gol",
            "year": 2021,
        },
    )
    assert vehicle.status_code == 201
    return customer_data, vehicle.json()


def _supplier(client, auth_headers, *, suffix: str):
    response = client.post(
        "/api/v1/admin/suppliers",
        headers=auth_headers,
        json={
            "name": f"Fornecedor {suffix}",
            "document": "04.252.011/0001-10",
            "email": f"fornecedor-{suffix}@test.com",
        },
    )
    assert response.status_code == 201
    return response.json()


def _product(client, auth_headers, supplier_id: int, *, sku: str, stock: int = 10):
    response = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={
            "name": f"Produto {sku}",
            "sku": sku,
            "unit_price": 10.0,
            "stock_quantity": stock,
            "supplier_id": supplier_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_open_service_order_expands_catalog_bom_and_reserves_stock(
    client,
    auth_headers,
    db_session,
):
    customer, vehicle = _customer_and_vehicle(client, auth_headers, suffix="bom")
    supplier = _supplier(client, auth_headers, suffix="bom")
    product = _product(client, auth_headers, supplier["id"], sku="BOM-OS-001")

    service = client.post(
        "/api/v1/admin/services",
        headers=auth_headers,
        json={"name": "Troca de óleo", "base_price": 100.0, "estimated_hours": 1.0},
    )
    assert service.status_code == 201
    service_id = service.json()["id"]

    bom = client.post(
        f"/api/v1/admin/services/{service_id}/product-lines",
        headers=auth_headers,
        json={"product_id": product["id"], "quantity": 2},
    )
    assert bom.status_code == 201

    opened = client.post(
        "/api/v1/admin/service-orders",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "vehicle_id": vehicle["id"],
            "services": [{"service_id": service_id, "quantity": 2}],
            "parts": [{"product_id": product["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 201
    service_order_id = opened.json()["service_order_id"]

    product_lines = db_session.scalars(
        select(ServiceOrderProductLineModel).where(
            ServiceOrderProductLineModel.service_order_id == service_order_id
        )
    ).all()
    assert [(line.product_id, line.quantity) for line in product_lines] == [
        (product["id"], 5)
    ]

    reservations = db_session.scalars(
        select(ReservationModel).where(
            ReservationModel.service_order_id == service_order_id
        )
    ).all()
    assert [(reservation.product_id, reservation.quantity) for reservation in reservations] == [
        (product["id"], 5)
    ]

    order = db_session.get(ServiceOrderModel, service_order_id)
    assert order is not None
    assert order.total_price == 250.0


def test_open_service_order_accepts_product_only_scope(client, auth_headers, db_session):
    customer, vehicle = _customer_and_vehicle(client, auth_headers, suffix="product-only")
    supplier = _supplier(client, auth_headers, suffix="product-only")
    product = _product(
        client,
        auth_headers,
        supplier["id"],
        sku="PART-ONLY-001",
        stock=3,
    )

    opened = client.post(
        "/api/v1/admin/service-orders",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "vehicle_id": vehicle["id"],
            "parts": [{"product_id": product["id"], "quantity": 2}],
        },
    )
    assert opened.status_code == 201
    service_order_id = opened.json()["service_order_id"]

    reservations = db_session.scalars(
        select(ReservationModel).where(
            ReservationModel.service_order_id == service_order_id
        )
    ).all()
    assert len(reservations) == 1
    assert reservations[0].product_id == product["id"]
    assert reservations[0].quantity == 2


def test_budget_approval_reserves_products_for_created_service_order(
    client,
    auth_headers,
    db_session,
):
    customer, vehicle = _customer_and_vehicle(client, auth_headers, suffix="budget")
    supplier = _supplier(client, auth_headers, suffix="budget")
    product = _product(client, auth_headers, supplier["id"], sku="BUDGET-OS-001")

    budget = client.post(
        "/api/v1/admin/budgets",
        headers=auth_headers,
        json={"customer_id": customer["id"], "vehicle_id": vehicle["id"]},
    )
    assert budget.status_code == 201
    budget_id = budget.json()["id"]

    line = client.post(
        f"/api/v1/admin/budgets/{budget_id}/product-lines",
        headers=auth_headers,
        json={"product_id": product["id"], "quantity": 2},
    )
    assert line.status_code == 201

    sent = client.post(
        f"/api/v1/admin/budgets/{budget_id}/send-email",
        headers=auth_headers,
    )
    assert sent.status_code == 200
    token = sent.json()["approval_token"]

    approved = client.post(f"/api/v1/public/budgets/{token}/approve")
    assert approved.status_code == 200

    orders = db_session.scalars(
        select(ServiceOrderModel).where(ServiceOrderModel.budget_id == budget_id)
    ).all()
    assert len(orders) == 1

    reservations = db_session.scalars(
        select(ReservationModel).where(
            ReservationModel.service_order_id == orders[0].id
        )
    ).all()
    assert [(reservation.product_id, reservation.quantity) for reservation in reservations] == [
        (product["id"], 2)
    ]
