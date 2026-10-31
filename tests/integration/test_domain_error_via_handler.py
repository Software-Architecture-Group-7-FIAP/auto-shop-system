from src.domain.exceptions import NotFoundError


def test_router_caught_domain_error_keeps_code_field(client, auth_headers, monkeypatch):
    class FailingService:
        def update(self, **kwargs):
            raise NotFoundError("OS não encontrada")

    monkeypatch.setattr(
        "src.api.routers.service_orders.compose_service_order_service",
        lambda db: FailingService(),
    )

    response = client.put(
        "/api/v1/admin/service-orders/999",
        headers={**auth_headers, "X-Correlation-ID": "domain-contract"},
        json={"mechanic_name": "Carlos"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "OS não encontrada", "code": "not_found"}
