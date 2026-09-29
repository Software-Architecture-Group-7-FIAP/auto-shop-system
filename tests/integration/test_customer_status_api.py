from tests.conftest import OPERATOR_CREDENTIALS, login


def _customer_payload():
    return {
        "name": "Maria Silva",
        "document": "529.982.247-25",
        "email": "maria@test.com",
        "phone": "11999999999",
        "address": "Rua A, 100",
    }


def _create_customer(client, auth_headers):
    response = client.post(
        "/api/v1/admin/customers", headers=auth_headers, json=_customer_payload()
    )
    assert response.status_code == 201
    return response.json()


def test_new_customer_defaults_to_active_in_admin_response(client, auth_headers):
    customer = _create_customer(client, auth_headers)

    assert customer["status"] == "Ativo"


def test_admin_can_inactivate_and_reactivate_customer(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    url = f"/api/v1/admin/customers/{customer['id']}/status"

    deactivated = client.patch(
        url, headers=auth_headers, json={"status": "Inativo"}
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "Inativo"

    persisted = client.get(
        f"/api/v1/admin/customers/{customer['id']}", headers=auth_headers
    )
    assert persisted.status_code == 200
    assert persisted.json()["status"] == "Inativo"

    reactivated = client.patch(
        url, headers=auth_headers, json={"status": "Ativo"}
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "Ativo"


def test_customer_status_change_requires_authentication(client):
    response = client.patch(
        "/api/v1/admin/customers/1/status", json={"status": "Inativo"}
    )

    assert response.status_code == 401


def test_operator_cannot_change_customer_status(client, second_client, auth_headers):
    customer = _create_customer(client, auth_headers)
    operator_headers = login(second_client, OPERATOR_CREDENTIALS)

    response = second_client.patch(
        f"/api/v1/admin/customers/{customer['id']}/status",
        headers=operator_headers,
        json={"status": "Inativo"},
    )

    assert response.status_code == 403
    unchanged = client.get(
        f"/api/v1/admin/customers/{customer['id']}", headers=auth_headers
    )
    assert unchanged.json()["status"] == "Ativo"


def test_customer_status_endpoint_rejects_unknown_status(client, auth_headers):
    customer = _create_customer(client, auth_headers)

    response = client.patch(
        f"/api/v1/admin/customers/{customer['id']}/status",
        headers=auth_headers,
        json={"status": "Suspenso"},
    )

    assert response.status_code == 422
    unchanged = client.get(
        f"/api/v1/admin/customers/{customer['id']}", headers=auth_headers
    )
    assert unchanged.json()["status"] == "Ativo"


def test_customer_status_endpoint_returns_not_found_for_unknown_customer(
    client, auth_headers
):
    response = client.patch(
        "/api/v1/admin/customers/999/status",
        headers=auth_headers,
        json={"status": "Inativo"},
    )

    assert response.status_code == 404


def test_public_customer_response_does_not_expose_status(client, auth_headers):
    customer = _create_customer(client, auth_headers)

    response = client.post(
        "/api/v1/customers/lookup",
        json={"document": "529.982.247-25", "email": "maria@test.com"},
    )

    assert response.status_code == 200
    assert response.json() == {"id": customer["id"], "name": "Maria Silva"}
