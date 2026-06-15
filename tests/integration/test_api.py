def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_customer_crud(client, auth_headers):
    create = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json={
            "name": "Maria Silva",
            "document": "529.982.247-25",
            "email": "maria@test.com",
            "phone": "11999999999",
        },
    )
    assert create.status_code == 201
    customer_id = create.json()["id"]

    get_doc = client.get("/api/v1/customers/by-document/52998224725")
    assert get_doc.status_code == 200

    update = client.put(
        f"/api/v1/admin/customers/{customer_id}",
        headers=auth_headers,
        json={"name": "Maria S."},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Maria S."


def test_vehicle_crud(client, auth_headers):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json={
            "name": "Pedro",
            "document": "529.982.247-25",
            "email": "pedro@test.com",
        },
    ).json()

    vehicle = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "plate": "ABC1D23",
            "brand": "VW",
            "model": "Gol",
            "year": 2021,
        },
    )
    assert vehicle.status_code == 201


def test_full_flow(client, auth_headers):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json={
            "name": "Ana",
            "document": "529.982.247-25",
            "email": "ana@test.com",
        },
    ).json()

    vehicle = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "plate": "XYZ9A87",
            "brand": "Toyota",
            "model": "Corolla",
            "year": 2022,
        },
    ).json()

    service = client.post(
        "/api/v1/admin/services",
        headers=auth_headers,
        json={"name": "Alinhamento", "base_price": 150.0, "estimated_hours": 1.5},
    ).json()

    product = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={"name": "Parafuso", "sku": "PAR-001", "unit_price": 5.0, "stock_quantity": 100},
    ).json()

    budget = client.post(
        "/api/v1/admin/budgets",
        headers=auth_headers,
        json={"customer_id": customer["id"], "vehicle_id": vehicle["id"]},
    ).json()

    client.post(
        f"/api/v1/admin/budgets/{budget['id']}/service-lines",
        headers=auth_headers,
        json={"service_id": service["id"], "quantity": 1},
    )
    client.post(
        f"/api/v1/admin/budgets/{budget['id']}/product-lines",
        headers=auth_headers,
        json={"product_id": product["id"], "quantity": 2},
    )

    updated_budget = client.get(
        f"/api/v1/admin/budgets/{budget['id']}",
        headers=auth_headers,
    ).json()
    assert updated_budget["total_price"] == 160.0

    send = client.post(
        f"/api/v1/admin/budgets/{budget['id']}/send-email",
        headers=auth_headers,
    )
    assert send.status_code == 200
    token = send.json().get("approval_token")
    assert token

    approve = client.get(f"/api/v1/public/budgets/{token}/approve")
    assert approve.status_code == 200

    orders = client.get("/api/v1/admin/service-orders", headers=auth_headers).json()
    assert len(orders) == 1
    os_id = orders[0]["id"]

    client.patch(
        f"/api/v1/admin/service-orders/{os_id}/assign-mechanic",
        headers=auth_headers,
        json={"mechanic_name": "Carlos"},
    )
    client.patch(
        f"/api/v1/admin/service-orders/{os_id}/start",
        headers=auth_headers,
    )
    client.patch(
        f"/api/v1/admin/service-orders/{os_id}/finish",
        headers=auth_headers,
    )

    invoice = client.post(
        f"/api/v1/admin/service-orders/{os_id}/invoice",
        headers=auth_headers,
    )
    assert invoice.status_code == 201

    paid = client.patch(
        f"/api/v1/admin/invoices/{invoice.json()['id']}/pay",
        headers=auth_headers,
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "Paga"

    track = client.get(
        f"/api/v1/public/service-orders/{os_id}?document=52998224725"
    )
    assert track.status_code == 200
    assert track.json()["status"] == "Entregue"


def test_admin_requires_auth(client):
    response = client.get("/api/v1/admin/customers")
    assert response.status_code == 401
