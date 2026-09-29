from src.domain.enums import BudgetStatus, ServiceOrderStatus


DECISIONS_URL = "/api/v1/public/budgets/decisions"


def _post_success(client, path: str, *, headers: dict[str, str], data: dict) -> dict:
    response = client.post(path, headers=headers, json=data)
    assert response.status_code in {200, 201}, response.text
    return response.json()


def _create_sent_budget(client, auth_headers, captured_emails) -> tuple[int, str]:
    customer = _post_success(
        client,
        "/api/v1/admin/customers",
        headers=auth_headers,
        data={
            "name": "Cliente Decisão",
            "document": "529.982.247-25",
            "email": "decisao@test.com",
            "address": "Rua Um, 100",
        },
    )
    vehicle = _post_success(
        client,
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        data={
            "customer_id": customer["id"],
            "plate": "DEC1A23",
            "state": "SP",
            "city": "São Paulo",
            "color": "Prata",
            "brand": "Fiat",
            "model": "Uno",
            "year": 2020,
        },
    )
    service = _post_success(
        client,
        "/api/v1/admin/services",
        headers=auth_headers,
        data={"name": "Diagnóstico", "base_price": 100.0, "estimated_hours": 1.0},
    )
    budget = _post_success(
        client,
        "/api/v1/admin/budgets",
        headers=auth_headers,
        data={"customer_id": customer["id"], "vehicle_id": vehicle["id"]},
    )
    _post_success(
        client,
        f"/api/v1/admin/budgets/{budget['id']}/service-lines",
        headers=auth_headers,
        data={"service_id": service["id"], "quantity": 1},
    )
    response = client.post(
        f"/api/v1/admin/budgets/{budget['id']}/send-email",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return budget["id"], captured_emails.approval_token()


def _decide(client, token: str, decision: str):
    return client.post(DECISIONS_URL, json={"token": token, "decision": decision})


def test_public_rejection_is_persisted_idempotent_and_cannot_be_flipped(
    client, auth_headers, captured_emails
):
    budget_id, token = _create_sent_budget(client, auth_headers, captured_emails)

    first = _decide(client, token, "reject")
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert first.json() == {
        "message": "Orçamento recusado.",
        "status": BudgetStatus.REJECTED.value,
        "already_processed": False,
        "service_order_id": None,
    }
    budget = client.get(f"/api/v1/admin/budgets/{budget_id}", headers=auth_headers)
    assert budget.status_code == 200
    assert budget.json()["status"] == BudgetStatus.REJECTED.value
    orders = client.get("/api/v1/admin/service-orders", headers=auth_headers)
    assert orders.status_code == 200
    assert orders.json()["items"] == []

    replay = _decide(client, token, "reject")
    assert replay.status_code == 200, replay.text
    assert replay.json()["already_processed"] is True
    assert replay.json()["status"] == BudgetStatus.REJECTED.value
    assert replay.json()["service_order_id"] is None

    opposite = _decide(client, token, "approve")
    assert opposite.status_code == 422
    assert client.get("/api/v1/admin/service-orders", headers=auth_headers).json()["items"] == []


def test_rejecting_sent_revision_returns_existing_order_to_diagnosis(
    client, auth_headers, captured_emails
):
    budget_id, token = _create_sent_budget(client, auth_headers, captured_emails)
    approved = _decide(client, token, "approve")
    assert approved.status_code == 200, approved.text
    order_id = approved.json()["service_order_id"]
    assert order_id is not None
    returned_to_diagnosis = client.patch(
        f"/api/v1/admin/service-orders/{order_id}/status-override",
        headers=auth_headers,
        json={
            "status": ServiceOrderStatus.EM_DIAGNOSTICO.value,
            "reason": "Novo diagnóstico necessário",
        },
    )
    assert returned_to_diagnosis.status_code == 200, returned_to_diagnosis.text
    assert returned_to_diagnosis.json()["status"] == ServiceOrderStatus.EM_DIAGNOSTICO.value

    revision = client.post(
        f"/api/v1/admin/budgets/{budget_id}/revisions", headers=auth_headers
    )
    assert revision.status_code == 201, revision.text
    revision_id = revision.json()["id"]
    captured_emails.clear()
    sent = client.post(
        f"/api/v1/admin/budgets/{revision_id}/send-email", headers=auth_headers
    )
    assert sent.status_code == 200, sent.text
    revision_token = captured_emails.approval_token()
    order_url = f"/api/v1/admin/service-orders/{order_id}"
    order_before_decision = client.get(order_url, headers=auth_headers)
    assert order_before_decision.status_code == 200
    assert order_before_decision.json()["status"] == ServiceOrderStatus.AGUARDANDO_APROVACAO.value

    rejected = _decide(client, revision_token, "reject")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == BudgetStatus.REJECTED.value
    assert rejected.json()["service_order_id"] is None
    order_after_decision = client.get(order_url, headers=auth_headers)
    assert order_after_decision.status_code == 200
    assert order_after_decision.json()["status"] == ServiceOrderStatus.EM_DIAGNOSTICO.value
    saved_revision = client.get(
        f"/api/v1/admin/budgets/{revision_id}", headers=auth_headers
    )
    assert saved_revision.status_code == 200
    assert saved_revision.json()["status"] == BudgetStatus.REJECTED.value

    replay = _decide(client, revision_token, "reject")
    assert replay.status_code == 200, replay.text
    assert replay.json()["already_processed"] is True
    order_after_replay = client.get(order_url, headers=auth_headers)
    assert order_after_replay.status_code == 200
    assert order_after_replay.json()["status"] == ServiceOrderStatus.EM_DIAGNOSTICO.value
