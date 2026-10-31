import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient

from src.config import settings
from src.domain.enums import ServiceOrderStatus
from src.infrastructure.database import (
    CustomerModel,
    ProductModel,
    ServiceModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
    ServiceOrderServiceLineModel,
    SupplierModel,
    VehicleModel,
)

ISSUER = "https://auth.example.invalid"
AUDIENCE = "auto-shop-api"


@pytest.fixture
def customer_token_factory(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_id = f"test-{uuid4().hex}"
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": key_id, "use": "sig", "alg": "RS256"})
    jwks = {"keys": [jwk]}
    monkeypatch.setattr(PyJWKClient, "fetch_data", lambda _client: jwks)
    monkeypatch.setattr(
        settings,
        "customer_jwt_jwks_url",
        f"https://auth.example.invalid/{key_id}",
    )
    monkeypatch.setattr(settings, "customer_jwt_issuer", ISSUER)
    monkeypatch.setattr(settings, "customer_jwt_audience", AUDIENCE)
    monkeypatch.setattr(settings, "customer_jwt_clock_skew_seconds", 0)

    def create_token(**overrides):
        now = datetime.now(timezone.utc)
        claims = {
            "sub": "42",
            "principal_type": "customer",
            "scope": "customer",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
            "jti": f"test-{uuid4().hex}",
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            private_key,
            algorithm="RS256",
            headers={"kid": key_id},
        )

    return create_token

def _create_customer_order(db_session, *, suffix: str) -> tuple[int, int]:
    customer = CustomerModel(
        name=f"Cliente {suffix}",
        email=f"cliente-{suffix}@test.local",
        address="Rua de teste",
    )
    db_session.add(customer)
    db_session.flush()

    vehicle = VehicleModel(
        customer_id=customer.id,
        plate=f"CUS{suffix[:3].upper()}1",
        state="SP",
        city="São Paulo",
        color="Azul",
        brand="Fiat",
        model="Uno",
        year=2020,
    )
    db_session.add(vehicle)
    db_session.flush()

    order = ServiceOrderModel(
        customer_id=customer.id,
        vehicle_id=vehicle.id,
        status=ServiceOrderStatus.EM_DIAGNOSTICO,
        total_price=125.0,
        created_at=datetime(2026, 10, 1, 12, 0, 0),
        started_at=datetime(2026, 10, 2, 12, 0, 0),
    )
    db_session.add(order)
    db_session.flush()
    return customer.id, order.id


def test_customer_can_read_own_service_order_with_allowlisted_fields(
    client,
    db_session,
    customer_token_factory,
):
    customer_id, order_id = _create_customer_order(db_session, suffix="own")
    service = ServiceModel(
        name="Alinhamento interno",
        description="Não deve aparecer no DTO",
        base_price=50.0,
        estimated_hours=1.0,
    )
    supplier = SupplierModel(
        name="Fornecedor interno",
        document="11222333000181",
        email="supplier-internal@test.local",
    )
    db_session.add_all([service, supplier])
    db_session.flush()
    product = ProductModel(
        name="Peça interna",
        description="Não deve aparecer no DTO",
        sku="CUSTOMER-DTO-001",
        unit_price=25.0,
        stock_quantity=10,
        supplier_id=supplier.id,
    )
    db_session.add(product)
    db_session.flush()
    db_session.add_all(
        [
            ServiceOrderServiceLineModel(
                service_order_id=order_id,
                service_id=service.id,
                quantity=2,
                unit_price=50.0,
            ),
            ServiceOrderProductLineModel(
                service_order_id=order_id,
                product_id=product.id,
                quantity=1,
                unit_price=25.0,
            ),
        ]
    )
    db_session.commit()
    token = customer_token_factory(sub=str(customer_id))

    response = client.get(
        f"/api/v1/customer/service-orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "id": order_id,
        "status": ServiceOrderStatus.EM_DIAGNOSTICO.value,
        "total_price": 125.0,
        "created_at": "2026-10-01T12:00:00",
        "started_at": "2026-10-02T12:00:00",
        "finished_at": None,
        "service_lines": [
            {"service_id": service.id, "quantity": 2, "unit_price": 50.0}
        ],
        "product_lines": [
            {"product_id": product.id, "quantity": 1, "unit_price": 25.0}
        ],
    }
    assert "customer_id" not in response.json()
    assert "vehicle_id" not in response.json()
    assert "budget_id" not in response.json()
    assert "mechanic_name" not in response.json()
    assert "cliente-own@test.local" not in response.text
    assert "Alinhamento interno" not in response.text
    assert "Fornecedor interno" not in response.text
    assert "supplier-internal@test.local" not in response.text


def test_customer_cannot_distinguish_foreign_service_order_from_missing_order(
    client,
    db_session,
    customer_token_factory,
    caplog,
):
    owner_id, foreign_order_id = _create_customer_order(db_session, suffix="owner")
    requester_id, _ = _create_customer_order(db_session, suffix="requester")
    db_session.commit()
    token = customer_token_factory(sub=str(requester_id))
    correlation_id = "0e8cf6ae-93a5-4bc5-a902-4ef9cb8d6a30"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": correlation_id,
    }

    foreign_response = client.get(
        f"/api/v1/customer/service-orders/{foreign_order_id}",
        headers=headers,
    )
    missing_response = client.get(
        "/api/v1/customer/service-orders/999999",
        headers=headers,
    )

    assert owner_id != requester_id
    assert foreign_response.status_code == 404
    assert missing_response.status_code == 404
    assert foreign_response.headers["cache-control"] == "no-store"
    assert missing_response.headers["cache-control"] == "no-store"
    assert foreign_response.json() == missing_response.json()
    assert foreign_response.json() == {
        "detail": "OS não encontrada",
        "code": "not_found",
    }
    assert "Cliente owner" not in foreign_response.text
    assert correlation_id in caplog.text
    assert "cliente-owner@test.local" not in caplog.text


def test_customer_service_order_requires_valid_customer_token(client):
    response = client.get("/api/v1/customer/service-orders/1")

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciais inválidas"


@pytest.mark.parametrize("service_order_id", [0, -1])
def test_customer_service_order_rejects_invalid_route_id(
    client,
    customer_token_factory,
    service_order_id,
):
    token = customer_token_factory()

    response = client.get(
        f"/api/v1/customer/service-orders/{service_order_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
