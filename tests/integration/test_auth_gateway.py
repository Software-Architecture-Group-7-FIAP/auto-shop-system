def test_gateway_login_returns_bearer_token(client):
    response = client.post(
        "/api/v1/auth/gateway-login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["username"] == "admin"
    assert isinstance(payload["access_token"], str) and payload["access_token"]
    assert payload["expires_in"] > 0


def test_admin_route_accepts_bearer_token(client):
    login = client.post(
        "/api/v1/auth/gateway-login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_admin_route_rejects_invalid_bearer_token(client):
    response = client.get(
        "/api/v1/admin/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
