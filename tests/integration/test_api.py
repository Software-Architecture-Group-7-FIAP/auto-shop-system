from unittest.mock import patch

from src.application.ports.cnpj_validator import CnpjValidationResult
from src.application.ports.cpf_validator import CpfValidationResult
from src.config import settings


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def _pf_customer_payload(**overrides):
    payload = {
        "name": "Maria Silva",
        "document": "529.982.247-25",
        "email": "maria@test.com",
        "phone": "11999999999",
        "address": "Rua A, 100",
    }
    payload.update(overrides)
    return payload


def _supplier_payload(**overrides):
    payload = {
        "name": "Fornecedor A",
        "document": "04.252.011/0001-10",
        "email": "fornecedor@test.com",
        "phone": "11999999999",
    }
    payload.update(overrides)
    return payload


def _vehicle_payload(customer_id: int, **overrides):
    payload = {
        "customer_id": customer_id,
        "plate": "ABC1D23",
        "state": "SP",
        "city": "São Paulo",
        "color": "Prata",
        "brand": "VW",
        "model": "Gol",
        "year": 2021,
    }
    payload.update(overrides)
    return payload


def _create_supplier(client, auth_headers, **overrides):
    return client.post(
        "/api/v1/admin/suppliers",
        headers=auth_headers,
        json=_supplier_payload(**overrides),
    ).json()


def test_login(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    assert response.json() == {"username": "admin", "role": "ADMIN"}
    # The session lives in cookies now; no token is handed to JavaScript.
    assert "access_token" not in response.text
    assert client.cookies.get("oficina_access")
    assert client.cookies.get("oficina_refresh")
    assert client.cookies.get("oficina_csrf")


def test_customer_crud(client, auth_headers):
    create = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(),
    )
    assert create.status_code == 201
    customer_id = create.json()["id"]
    assert create.json()["documents"] == ["52998224725"]
    assert create.json()["address"] == "Rua A, 100"

    get_doc = client.post(
        "/api/v1/customers/lookup",
        json={"document": "52998224725", "email": "maria@test.com"},
    )
    assert get_doc.status_code == 200
    assert get_doc.json() == {"id": customer_id, "name": "Maria Silva"}

    wrong_factor = client.post(
        "/api/v1/customers/lookup",
        json={"document": "52998224725", "email": "wrong@test.com"},
    )
    assert wrong_factor.status_code == 404

    old_public_lookup = client.get("/api/v1/customers/by-document/52998224725")
    assert old_public_lookup.status_code == 404

    old_admin_lookup = client.get(
        "/api/v1/admin/customers/by-document/52998224725",
        headers=auth_headers,
    )
    assert old_admin_lookup.status_code in {404, 405}

    get_admin_doc = client.post(
        "/api/v1/admin/customers/by-document",
        headers=auth_headers,
        json={"document": "52998224725"},
    )
    assert get_admin_doc.status_code == 200

    update = client.put(
        f"/api/v1/admin/customers/{customer_id}",
        headers=auth_headers,
        json={"name": "Maria S.", "address": "Rua B, 200"},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Maria S."
    assert update.json()["address"] == "Rua B, 200"

    delete = client.delete(
        f"/api/v1/admin/customers/{customer_id}",
        headers=auth_headers,
    )
    assert delete.status_code == 204


def test_customer_rejects_invalid_document(client, auth_headers):
    response = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(document="123"),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Documento inválido"


def test_customer_rejects_empty_address(client, auth_headers):
    response = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(address=""),
    )
    assert response.status_code == 422


def test_customer_rejects_duplicate_document(client, auth_headers):
    client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(),
    )
    response = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(name="Maria 2", email="maria2@test.com"),
    )
    assert response.status_code == 409


def test_customer_public_lookup_not_found(client):
    response = client.post(
        "/api/v1/customers/lookup",
        json={"document": "52998224725", "email": "maria@test.com"},
    )
    assert response.status_code == 404


def test_admin_requires_valid_token(client):
    response = client.get(
        "/api/v1/admin/customers",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


def test_vehicle_crud(client, auth_headers):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(name="Pedro", email="pedro@test.com", phone=None),
    ).json()

    create = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json=_vehicle_payload(customer["id"]),
    )
    assert create.status_code == 201
    vehicle = create.json()
    assert vehicle["state"] == "SP"
    assert vehicle["city"] == "São Paulo"
    assert vehicle["color"] == "Prata"

    listed = client.get(
        f"/api/v1/admin/customers/{customer['id']}/vehicles",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["plate"] == "ABC1D23"

    updated = client.put(
        f"/api/v1/admin/vehicles/{vehicle['id']}",
        headers=auth_headers,
        json={"color": "Preto"},
    )
    assert updated.status_code == 200
    assert updated.json()["color"] == "Preto"

    deleted = client.delete(
        f"/api/v1/admin/vehicles/{vehicle['id']}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204


def test_vehicle_rejects_invalid_plate(client, auth_headers):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(name="Pedro", email="pedro2@test.com", phone=None),
    ).json()

    response = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json=_vehicle_payload(customer["id"], plate="INVALID"),
    )
    assert response.status_code == 422
    assert "Veículo inválido" in response.json()["detail"]


def test_vehicle_rejects_duplicate_plate_for_same_customer(client, auth_headers):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(name="Pedro", email="pedro3@test.com", phone=None),
    ).json()

    first = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json=_vehicle_payload(customer["id"]),
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json=_vehicle_payload(customer["id"], brand="Fiat", model="Uno"),
    )
    assert duplicate.status_code == 409


def test_customer_vehicles_requires_auth(client, auth_headers, second_client):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(name="Pedro", email="pedro4@test.com", phone=None),
    ).json()

    response = second_client.get(f"/api/v1/admin/customers/{customer['id']}/vehicles")
    assert response.status_code == 401


def test_service_catalog_crud_and_product_lines(client, auth_headers):
    create = client.post(
        "/api/v1/admin/services",
        headers=auth_headers,
        json={"name": "Alinhamento", "base_price": 150.0, "estimated_hours": 1.5},
    )
    assert create.status_code == 201
    service_id = create.json()["id"]

    listed = client.get("/api/v1/admin/services", headers=auth_headers)
    assert listed.status_code == 200
    assert any(service["id"] == service_id for service in listed.json())

    found = client.get(f"/api/v1/admin/services/{service_id}", headers=auth_headers)
    assert found.status_code == 200
    assert found.json()["name"] == "Alinhamento"

    update = client.put(
        f"/api/v1/admin/services/{service_id}",
        headers=auth_headers,
        json={"description": "Serviço completo", "base_price": 175.0},
    )
    assert update.status_code == 200
    assert update.json()["description"] == "Serviço completo"
    assert update.json()["base_price"] == 175.0

    supplier = _create_supplier(client, auth_headers)

    product = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={
            "name": "Parafuso",
            "sku": "PAR-SERV-001",
            "unit_price": 5.0,
            "stock_quantity": 100,
            "supplier_id": supplier["id"],
        },
    )
    assert product.status_code == 201

    line = client.post(
        f"/api/v1/admin/services/{service_id}/product-lines",
        headers=auth_headers,
        json={"product_id": product.json()["id"], "quantity": 2},
    )
    assert line.status_code == 201
    assert line.json()["service_id"] == service_id
    assert line.json()["quantity"] == 2

    increased_line = client.post(
        f"/api/v1/admin/services/{service_id}/product-lines",
        headers=auth_headers,
        json={"product_id": product.json()["id"], "quantity": 1},
    )
    assert increased_line.status_code == 201
    assert increased_line.json()["id"] == line.json()["id"]
    assert increased_line.json()["quantity"] == 3

    found_with_lines = client.get(f"/api/v1/admin/services/{service_id}", headers=auth_headers)
    assert found_with_lines.status_code == 200
    assert found_with_lines.json()["product_lines"] == [
        {
            "id": line.json()["id"],
            "service_id": service_id,
            "product_id": product.json()["id"],
            "quantity": 3,
        }
    ]

    delete_line = client.delete(
        f"/api/v1/admin/services/{service_id}/product-lines/{line.json()['id']}",
        headers=auth_headers,
    )
    assert delete_line.status_code == 204

    line = client.post(
        f"/api/v1/admin/services/{service_id}/product-lines",
        headers=auth_headers,
        json={"product_id": product.json()["id"], "quantity": 1},
    )
    assert line.status_code == 201

    delete = client.delete(f"/api/v1/admin/services/{service_id}", headers=auth_headers)
    assert delete.status_code == 204

    missing = client.get(f"/api/v1/admin/services/{service_id}", headers=auth_headers)
    assert missing.status_code == 404


def test_products_and_suppliers_crud(client, auth_headers):
    supplier = client.post(
        "/api/v1/admin/suppliers",
        headers=auth_headers,
        json={
            **_supplier_payload(),
        },
    )
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]
    assert supplier.json()["document"] == "04252011000110"

    listed_suppliers = client.get("/api/v1/admin/suppliers", headers=auth_headers)
    assert listed_suppliers.status_code == 200
    assert any(item["id"] == supplier_id for item in listed_suppliers.json())

    found_supplier = client.get(
        f"/api/v1/admin/suppliers/{supplier_id}",
        headers=auth_headers,
    )
    assert found_supplier.status_code == 200

    updated_supplier = client.put(
        f"/api/v1/admin/suppliers/{supplier_id}",
        headers=auth_headers,
        json={"name": "Fornecedor B"},
    )
    assert updated_supplier.status_code == 200
    assert updated_supplier.json()["name"] == "Fornecedor B"

    product = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={
            "name": "Óleo 5W30",
            "sku": "OLEO-API-001",
            "unit_price": 50.0,
            "stock_quantity": 10,
            "description": "Lubrificante",
            "supplier_id": supplier_id,
        },
    )
    assert product.status_code == 201
    product_id = product.json()["id"]

    duplicate = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={
            "name": "Óleo",
            "sku": "OLEO-API-001",
            "unit_price": 55.0,
            "supplier_id": supplier_id,
        },
    )
    assert duplicate.status_code == 409

    missing_supplier = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={"name": "Filtro", "sku": "FILTRO-API-001", "unit_price": 30.0},
    )
    assert missing_supplier.status_code == 422

    linked_supplier_delete = client.delete(
        f"/api/v1/admin/suppliers/{supplier_id}",
        headers=auth_headers,
    )
    assert linked_supplier_delete.status_code == 409

    listed_products = client.get("/api/v1/admin/products", headers=auth_headers)
    assert listed_products.status_code == 200
    assert any(item["id"] == product_id for item in listed_products.json())

    found_product = client.get(
        f"/api/v1/admin/products/{product_id}",
        headers=auth_headers,
    )
    assert found_product.status_code == 200
    assert found_product.json()["sku"] == "OLEO-API-001"

    updated_product = client.put(
        f"/api/v1/admin/products/{product_id}",
        headers=auth_headers,
        json={"name": "Óleo premium", "unit_price": 75.0},
    )
    assert updated_product.status_code == 200
    assert updated_product.json()["name"] == "Óleo premium"
    assert updated_product.json()["unit_price"] == 75.0

    stock = client.patch(
        f"/api/v1/admin/products/{product_id}/stock",
        headers=auth_headers,
        json={"quantity": -3},
    )
    assert stock.status_code == 200
    assert stock.json()["stock_quantity"] == 7

    insufficient_stock = client.patch(
        f"/api/v1/admin/products/{product_id}/stock",
        headers=auth_headers,
        json={"quantity": -8},
    )
    assert insufficient_stock.status_code == 422

    delete_product = client.delete(
        f"/api/v1/admin/products/{product_id}",
        headers=auth_headers,
    )
    assert delete_product.status_code == 204

    delete_supplier = client.delete(
        f"/api/v1/admin/suppliers/{supplier_id}",
        headers=auth_headers,
    )
    assert delete_supplier.status_code == 204


def _os_status(client, auth_headers, os_id: int) -> str:
    return client.get(
        f"/api/v1/admin/service-orders/{os_id}",
        headers=auth_headers,
    ).json()["status"]


def test_full_flow(client, auth_headers, captured_emails):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(name="Ana", email="ana@test.com", phone=None),
    ).json()

    vehicle = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json=_vehicle_payload(customer["id"], plate="XYZ9A87", brand="Toyota", model="Corolla", year=2022),
    ).json()

    service = client.post(
        "/api/v1/admin/services",
        headers=auth_headers,
        json={"name": "Alinhamento", "base_price": 150.0, "estimated_hours": 1.5},
    ).json()

    supplier = _create_supplier(client, auth_headers)

    product = client.post(
        "/api/v1/admin/products",
        headers=auth_headers,
        json={
            "name": "Parafuso",
            "sku": "PAR-001",
            "unit_price": 5.0,
            "stock_quantity": 100,
            "supplier_id": supplier["id"],
        },
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

    availability = client.get(
        f"/api/v1/admin/budgets/{budget['id']}/availability",
        headers=auth_headers,
    )
    assert availability.status_code == 200
    assert availability.json()[0]["sufficient"] is True

    estimated_delivery = client.get(
        f"/api/v1/admin/budgets/{budget['id']}/estimated-delivery",
        headers=auth_headers,
    )
    assert estimated_delivery.status_code == 200
    assert estimated_delivery.json()["estimated_delivery"]

    send = client.post(
        f"/api/v1/admin/budgets/{budget['id']}/send-email",
        headers=auth_headers,
    )
    assert send.status_code == 200
    # The raw bearer token is never returned by the API; it exists only in
    # the e-mail link.
    assert "approval_token" not in send.json()
    token = captured_emails.approval_token()

    get_approve = client.get(f"/api/v1/public/budgets/{token}/approve")
    assert get_approve.status_code in {404, 405}

    get_reject = client.get(f"/api/v1/public/budgets/{token}/reject")
    assert get_reject.status_code in {404, 405}

    budget_after_get = client.get(
        f"/api/v1/admin/budgets/{budget['id']}",
        headers=auth_headers,
    ).json()
    assert budget_after_get["status"] == "Enviado"

    orders_after_get = client.get("/api/v1/admin/service-orders", headers=auth_headers).json()
    assert orders_after_get == []

    approve = client.post(
        "/api/v1/public/budgets/decisions",
        json={"token": token, "decision": "approve"},
    )
    assert approve.status_code == 200

    orders = client.get("/api/v1/admin/service-orders", headers=auth_headers).json()
    assert len(orders) == 1
    os_id = orders[0]["id"]

    assign = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/assign-mechanic",
        headers=auth_headers,
        json={"mechanic_name": "Carlos"},
    )
    assert assign.status_code == 200
    assert assign.json()["status"] == "Em diagnóstico"

    priority = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/priority",
        headers=auth_headers,
        json={"priority": "Alta"},
    )
    assert priority.status_code == 200
    assert priority.json()["priority"] == "Alta"

    swap_without_reason = client.put(
        f"/api/v1/admin/service-orders/{os_id}",
        headers=auth_headers,
        json={"mechanic_name": "Carlos Silva", "priority": "Urgente"},
    )
    assert swap_without_reason.status_code == 422

    updated_os = client.put(
        f"/api/v1/admin/service-orders/{os_id}",
        headers=auth_headers,
        json={
            "mechanic_name": "Carlos Silva",
            "priority": "Urgente",
            "reason": "Mecânico original de férias",
        },
    )
    assert updated_os.status_code == 200
    assert updated_os.json()["mechanic_name"] == "Carlos Silva"
    assert updated_os.json()["priority"] == "Urgente"
    assert updated_os.json()["status"] == "Em diagnóstico"

    generic_status_update = client.put(
        f"/api/v1/admin/service-orders/{os_id}",
        headers=auth_headers,
        json={"status": "Finalizada"},
    )
    assert generic_status_update.status_code == 422

    # Break-glass only moves between the pre-execution states, and only for
    # an admin.
    same_status_override = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/status-override",
        headers=auth_headers,
        json={
            "status": "Em diagnóstico",
            "reason": "Correção administrativa no fluxo de teste",
        },
    )
    assert same_status_override.status_code == 422

    forward_override = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/status-override",
        headers=auth_headers,
        json={
            "status": "Finalizada",
            "reason": "Correção administrativa no fluxo de teste",
        },
    )
    assert forward_override.status_code == 422

    status_override = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/status-override",
        headers=auth_headers,
        json={
            "status": "Recebida",
            "reason": "Correção administrativa no fluxo de teste",
        },
    )
    assert status_override.status_code == 200
    assert status_override.json()["status"] == "Recebida"

    restore_override = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/status-override",
        headers=auth_headers,
        json={
            "status": "Em diagnóstico",
            "reason": "Retomando o diagnóstico",
        },
    )
    assert restore_override.status_code == 200

    no_op_update = client.put(
        f"/api/v1/admin/service-orders/{os_id}",
        headers=auth_headers,
        json={},
    )
    assert no_op_update.status_code == 422

    # Reaching the execution queue goes through the workflow: a revision is
    # sent for approval, and the customer's approval advances the OS.
    revision = client.post(
        f"/api/v1/admin/budgets/{budget['id']}/revisions",
        headers=auth_headers,
    )
    assert revision.status_code == 201
    revision_id = revision.json()["id"]

    captured_emails.clear()
    send_revision = client.post(
        f"/api/v1/admin/budgets/{revision_id}/send-email",
        headers=auth_headers,
    )
    assert send_revision.status_code == 200
    assert _os_status(client, auth_headers, os_id) == "Aguardando aprovação"

    approve_revision = client.post(
        "/api/v1/public/budgets/decisions",
        json={"token": captured_emails.approval_token(), "decision": "approve"},
    )
    assert approve_revision.status_code == 200
    assert _os_status(client, auth_headers, os_id) == "Aguardando início"

    with patch(
        "src.infrastructure.auth.service_order_tracking.HmacServiceOrderTrackingTokenService.create_token",
        return_value="service-order-tracking-token",
    ):
        send_os = client.post(
            f"/api/v1/admin/service-orders/{os_id}/send-email",
            headers=auth_headers,
        )
    assert send_os.status_code == 200

    reservations = client.post(
        f"/api/v1/admin/reservations/os/{os_id}",
        headers=auth_headers,
    )
    assert reservations.status_code == 201

    client.patch(
        f"/api/v1/admin/service-orders/{os_id}/start",
        headers=auth_headers,
    )

    withdrawal = client.post(
        "/api/v1/admin/stock-withdrawals",
        headers=auth_headers,
        json={"service_order_id": os_id, "product_id": product["id"], "quantity": 2},
    )
    assert withdrawal.status_code == 201

    blocked_finish = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/finish",
        headers=auth_headers,
    )
    assert blocked_finish.status_code == 422

    fulfill = client.patch(
        f"/api/v1/admin/stock-withdrawals/{withdrawal.json()['id']}/fulfill",
        headers=auth_headers,
    )
    assert fulfill.status_code == 200
    assert fulfill.json()["status"] == "Atendida"

    finish = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/finish",
        headers=auth_headers,
    )
    assert finish.status_code == 200
    assert finish.json()["status"] == "Finalizada"

    invoice = client.post(
        f"/api/v1/admin/service-orders/{os_id}/invoice",
        headers=auth_headers,
    )
    assert invoice.status_code == 201
    assert invoice.json()["amount"] == 160.0

    invoice_lookup = client.get(
        f"/api/v1/admin/service-orders/{os_id}/invoice",
        headers=auth_headers,
    )
    assert invoice_lookup.status_code == 200
    assert invoice_lookup.json()["id"] == invoice.json()["id"]

    paid = client.patch(
        f"/api/v1/admin/invoices/{invoice.json()['id']}/pay",
        headers=auth_headers,
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "Paga"

    deliver = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/deliver",
        headers=auth_headers,
    )
    assert deliver.status_code == 422

    old_track = client.get(f"/api/v1/public/service-orders/{os_id}?document=52998224725")
    assert old_track.status_code in {404, 405}

    deliver = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/deliver",
        headers=auth_headers,
    )
    assert deliver.status_code == 422

    old_track_route = client.get(
        "/api/v1/public/service-orders/track/service-order-tracking-token"
    )
    assert old_track_route.status_code in {404, 405}

    track = client.post(
        "/api/v1/public/service-orders/track",
        json={"token": captured_emails.tracking_token()},
    )
    assert track.status_code == 200
    assert track.json()["status"] == "Entregue"
    assert "mechanic_name" not in track.json()
    assert "priority" not in track.json()


def test_execution_queue_orders_pending_service_orders_by_priority(client, auth_headers, captured_emails):
    customer = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(name="Bruno", email="bruno@test.com", phone=None),
    ).json()

    service = client.post(
        "/api/v1/admin/services",
        headers=auth_headers,
        json={"name": "Troca de óleo", "base_price": 100.0, "estimated_hours": 1.0},
    ).json()

    def _create_approved_os(plate: str) -> dict:
        vehicle = client.post(
            "/api/v1/admin/vehicles",
            headers=auth_headers,
            json=_vehicle_payload(
                customer["id"],
                plate=plate,
                brand="Toyota",
                model="Corolla",
                year=2022,
            ),
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
            f"/api/v1/admin/budgets/{budget['id']}/send-email",
            headers=auth_headers,
        )
        client.post(
            "/api/v1/public/budgets/decisions",
            json={"token": captured_emails.approval_token(), "decision": "approve"},
        )
        captured_emails.clear()
        orders = client.get("/api/v1/admin/service-orders", headers=auth_headers).json()
        order = next(o for o in orders if o["vehicle_id"] == vehicle["id"])

        # The OS only reaches the queue after a mechanic diagnoses it and the
        # customer approves the resulting revision.
        client.patch(
            f"/api/v1/admin/service-orders/{order['id']}/assign-mechanic",
            headers=auth_headers,
            json={"mechanic_name": "Carlos"},
        )
        revision = client.post(
            f"/api/v1/admin/budgets/{budget['id']}/revisions",
            headers=auth_headers,
        ).json()
        client.post(
            f"/api/v1/admin/budgets/{revision['id']}/send-email",
            headers=auth_headers,
        )
        client.post(
            "/api/v1/public/budgets/decisions",
            json={"token": captured_emails.approval_token(), "decision": "approve"},
        )
        captured_emails.clear()
        assert _os_status(client, auth_headers, order["id"]) == "Aguardando início"
        return order

    low_priority_os = _create_approved_os("LOW1A23")
    urgent_os = _create_approved_os("URG2B34")

    set_priority = client.patch(
        f"/api/v1/admin/service-orders/{urgent_os['id']}/priority",
        headers=auth_headers,
        json={"priority": "Urgente"},
    )
    assert set_priority.status_code == 200

    queue = client.get("/api/v1/admin/service-orders/queue", headers=auth_headers)
    assert queue.status_code == 200
    queue_ids = [order["id"] for order in queue.json()]
    assert urgent_os["id"] in queue_ids
    assert low_priority_os["id"] in queue_ids
    assert queue_ids.index(urgent_os["id"]) < queue_ids.index(low_priority_os["id"])


@patch("src.infrastructure.external.brasil_api_cnpj.HttpBrasilApiCnpjValidator.validate")
def test_validate_and_create_pj_customer(mock_validate, client, auth_headers):
    mock_validate.return_value = CnpjValidationResult(
        valid=True,
        legal_name="Empresa LTDA",
        trade_name="Empresa",
    )

    validate = client.post(
        "/api/v1/admin/customers/validate-cnpj",
        headers=auth_headers,
        json={"document": "04252011000110"},
    )
    assert validate.status_code == 200
    assert validate.json()["valid"] is True
    assert validate.json()["legal_name"] == "Empresa LTDA"

    create = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json={
            "name": "Empresa LTDA",
            "document": "04.252.011/0001-10",
            "email": "empresa@test.com",
            "address": "Av. B, 200",
        },
    )
    assert create.status_code == 201
    assert create.json()["documents"] == ["04252011000110"]
    assert mock_validate.call_count == 2


@patch("src.infrastructure.external.invertexto_cpf.HttpInvertextoCpfValidator.validate")
def test_validate_and_create_pf_customer(mock_validate, client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "invertexto_api_token", "test-token")
    monkeypatch.setattr(settings, "skip_cpf_external_validation", False)
    mock_validate.return_value = CpfValidationResult(
        valid=True,
        formatted="529.982.247-25",
    )

    validate = client.post(
        "/api/v1/admin/customers/validate-cpf",
        headers=auth_headers,
        json={"document": "52998224725"},
    )
    assert validate.status_code == 200
    assert validate.json()["valid"] is True
    assert validate.json()["formatted"] == "529.982.247-25"

    create = client.post(
        "/api/v1/admin/customers",
        headers=auth_headers,
        json=_pf_customer_payload(),
    )
    assert create.status_code == 201
    assert create.json()["documents"] == ["52998224725"]
    assert mock_validate.call_count == 2


def test_admin_requires_auth(client):
    response = client.get("/api/v1/admin/customers")
    assert response.status_code == 401
