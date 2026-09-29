import pytest

from src.domain.exceptions import (
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)


class FailingServiceOrderService:
    def __init__(self, error: DomainError):
        self.error = error

    def get_by_id(self, service_order_id: int):
        raise self.error


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (NotFoundError("OS não encontrada"), 404),
        (ValidationError("Transição inválida"), 422),
        (ConflictError("OS em conflito"), 409),
        (UnauthorizedError("Sessão inválida"), 401),
        (ForbiddenError("Acesso negado"), 403),
        (ServiceUnavailableError("Serviço indisponível"), 503),
        (DomainError("Erro de domínio"), 400),
    ],
)
def test_router_domain_errors_use_global_http_contract(
    client, auth_headers, monkeypatch, error, status_code
):
    monkeypatch.setattr(
        "src.api.routers.service_orders.compose_service_order_service",
        lambda db: FailingServiceOrderService(error),
    )

    response = client.get("/api/v1/admin/service-orders/999", headers=auth_headers)

    assert response.status_code == status_code
    assert response.json() == {"detail": error.message, "code": error.code}


def test_auth_dependency_domain_error_uses_global_http_contract(client, auth_headers):
    client.cookies.set("oficina_access", "invalid-access-token")

    response = client.get("/api/v1/admin/me", headers=auth_headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Token inválido", "code": "unauthorized"}


def test_public_customer_lookup_keeps_generic_response(client):
    response = client.post(
        "/api/v1/customers/lookup",
        json={"document": "52998224725", "email": "maria@test.com"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Cliente não encontrado"}
