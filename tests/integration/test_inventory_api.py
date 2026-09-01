def _create_os_with_product(
    client, auth_headers, captured_emails, stock_quantity: int, product_quantity: int
):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json={
            "name": "Cliente Estoque",
            "document": "529.982.247-25",
            "email": "estoque@test.com",
            "address": "Rua Estoque, 1",
        },
    ).json()

    vehicle = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "plate": "EST1A23",
            "state": "SP",
            "city": "São Paulo",
            "color": "Prata",
            "brand": "Fiat",
            "model": "Uno",
            "year": 2020,
        },
    ).json()

    supplier = client.post(
        "/api/v1/admin/suppliers",
        headers=auth_headers,
        json={
            "name": "Fornecedor Estoque",
            "document": "04.252.011/0001-10",
            "email": "fornecedor-estoque@test.com",
        },
    ).json()

    product = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={
            "name": "Peça reservável",
            "sku": "PEC-RES-001",
            "unit_price": 25.0,
            "stock_quantity": stock_quantity,
            "supplier_id": supplier["id"],
        },
    ).json()

    budget = client.post(
        "/api/v1/admin/budgets",
        headers=auth_headers,
        json={"customer_id": customer["id"], "vehicle_id": vehicle["id"]},
    ).json()

    client.post(
        f"/api/v1/admin/budgets/{budget['id']}/product-lines",
        headers=auth_headers,
        json={"product_id": product["id"], "quantity": product_quantity},
    )

    client.post(
        f"/api/v1/admin/budgets/{budget['id']}/send-email",
        headers=auth_headers,
    )
    token = captured_emails.approval_token()
    approve = client.post(
        "/api/v1/public/budgets/decisions",
        json={"token": token, "decision": "approve"},
    )
    assert approve.status_code == 200

    service_orders = client.get(
        "/api/v1/admin/service-orders",
        headers=auth_headers,
    )
    assert service_orders.status_code == 200
    assert len(service_orders.json()["items"]) == 1
    service_order_id = service_orders.json()["items"][0]["id"]

    return {
        "product_id": product["id"],
        "service_order_id": service_order_id,
    }


def test_inventory_reservations_and_purchase_requests_flow(client, auth_headers, captured_emails):
    context = _create_os_with_product(
        client,
        auth_headers,
        captured_emails,
        stock_quantity=1,
        product_quantity=5,
    )

    create_reservations = client.post(
        "/api/v1/admin/reservations",
        headers=auth_headers,
        json={"service_order_id": context["service_order_id"]},
    )
    assert create_reservations.status_code == 201
    reservations = create_reservations.json()
    assert len(reservations) == 1
    assert reservations[0]["product_id"] == context["product_id"]
    assert reservations[0]["quantity"] == 5
    assert reservations[0]["service_order_id"] == context["service_order_id"]

    list_reservations = client.get("/api/v1/admin/reservations", headers=auth_headers)
    assert list_reservations.status_code == 200
    assert len(list_reservations.json()) == 1

    purchase_requests = client.get(
        "/api/v1/admin/purchase-requests",
        headers=auth_headers,
    )
    assert purchase_requests.status_code == 200
    assert len(purchase_requests.json()) == 1
    assert purchase_requests.json()[0]["product_id"] == context["product_id"]
    assert purchase_requests.json()[0]["quantity"] == 4
    assert purchase_requests.json()[0]["service_order_id"] == context["service_order_id"]

    pending = client.get(
        f"/api/v1/admin/products/{context['product_id']}/pending-receipts",
        headers=auth_headers,
    )
    assert pending.status_code == 200
    assert len(pending.json()) == 1
    purchase_request_id = pending.json()[0]["id"]

    receipt = client.post(
        f"/api/v1/admin/purchase-requests/{purchase_request_id}/receipt",
        headers=auth_headers,
        json={"quantity": 4},
    )
    assert receipt.status_code == 201
    assert receipt.json()["quantity"] == 4

    product = client.get(
        f"/api/v1/admin/products/{context['product_id']}",
        headers=auth_headers,
    )
    assert product.status_code == 200
    assert product.json()["stock_quantity"] == 5

    pending_after_receipt = client.get(
        f"/api/v1/admin/products/{context['product_id']}/pending-receipts",
        headers=auth_headers,
    )
    assert pending_after_receipt.status_code == 200
    assert pending_after_receipt.json() == []


def test_inventory_create_purchase_request_and_reject_missing_os(client, auth_headers):
    supplier = client.post(
        "/api/v1/admin/suppliers",
        headers=auth_headers,
        json={
            "name": "Fornecedor Manual",
            "document": "04.252.011/0001-10",
            "email": "manual@test.com",
        },
    ).json()

    product = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={
            "name": "Peça manual",
            "sku": "PEC-MAN-001",
            "unit_price": 10.0,
            "stock_quantity": 0,
            "supplier_id": supplier["id"],
        },
    ).json()

    create_request = client.post(
        "/api/v1/admin/purchase-requests",
        headers=auth_headers,
        json={"product_id": product["id"], "quantity": 3},
    )
    assert create_request.status_code == 201
    assert create_request.json()["product_id"] == product["id"]
    assert create_request.json()["quantity"] == 3

    missing_os = client.post(
        "/api/v1/admin/reservations",
        headers=auth_headers,
        json={"service_order_id": 9999},
    )
    assert missing_os.status_code == 404


def test_inventory_requires_auth(client):
    response = client.get("/api/v1/admin/reservations")
    assert response.status_code == 401
