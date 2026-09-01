"""Coverage for the cookie session, CSRF, and role surface added by the
security hardening pass. These paths carry the whole authentication story, so
they are exercised end to end rather than through the services alone."""

import pytest

from src.api import rate_limit
from src.api.auth_cookies import ACCESS_COOKIE_PATH
from src.api.rate_limit import RateLimitPolicy, login_rate_limiter
from src.config import settings
from tests.conftest import (
    ACCESS_COOKIE,
    ADMIN_CREDENTIALS,
    CSRF_COOKIE,
    OPERATOR_CREDENTIALS,
    REFRESH_COOKIE,
    csrf_headers,
    login,
)

CUSTOMER_PAYLOAD = {
    "name": "Cliente CSRF",
    "document": "529.982.247-25",
    "email": "csrf@test.com",
    "address": "Rua CSRF, 1",
}


def _cookie_header(response, name: str) -> str:
    for header in reversed(response.headers.get_list("set-cookie")):
        if header.startswith(f"{name}="):
            return header
    raise AssertionError(f"{name} was not set")


# --------------------------------------------------------------- cookie shape


def test_login_sets_httponly_session_cookies_and_a_readable_csrf_cookie(client):
    response = client.post("/api/v1/auth/login", json=ADMIN_CREDENTIALS)

    access = _cookie_header(response, ACCESS_COOKIE)
    refresh = _cookie_header(response, REFRESH_COOKIE)
    csrf = _cookie_header(response, CSRF_COOKIE)

    assert "HttpOnly" in access
    assert "HttpOnly" in refresh
    # The double-submit token has to be readable by the frontend.
    assert "HttpOnly" not in csrf
    assert "samesite=lax" in access.lower()
    assert "Path=/api/v1/admin" in access
    # The refresh cookie is only ever sent to the auth endpoints.
    assert "Path=/api/v1/auth" in refresh
    assert response.headers["cache-control"] == "no-store"


def test_session_cookies_are_not_marked_secure_outside_production(client):
    response = client.post("/api/v1/auth/login", json=ADMIN_CREDENTIALS)

    assert "Secure" not in _cookie_header(response, ACCESS_COOKIE)


def test_environments_are_production_like_unless_explicitly_a_dev_one(monkeypatch):
    """A typo such as APP_ENV=prd must not silently drop the Secure flag."""
    for env in ("production", "staging", "prd", "homolog", "hml", "whatever"):
        monkeypatch.setattr(settings, "app_env", env)
        assert settings.is_production_like() is True

    for env in ("development", "dev", "local", "test", "testing"):
        monkeypatch.setattr(settings, "app_env", env)
        assert settings.is_production_like() is False


# ---------------------------------------------------------------------- CSRF


def test_state_changing_request_without_csrf_header_is_rejected(client, auth_headers):
    response = client.post("/api/v1/admin/customers", json=CUSTOMER_PAYLOAD)

    assert response.status_code == 403
    assert response.json()["detail"] == "Origem não permitida"


def test_state_changing_request_with_a_mismatched_csrf_header_is_rejected(
    client, auth_headers
):
    response = client.post(
        "/api/v1/admin/customers",
        headers={"X-CSRF-Token": "not-the-cookie", "Origin": "http://testserver"},
        json=CUSTOMER_PAYLOAD,
    )

    assert response.status_code == 403


def test_read_only_requests_do_not_need_a_csrf_header(client, auth_headers):
    assert client.get("/api/v1/admin/customers").status_code == 200


def test_request_from_a_foreign_origin_is_rejected(client, auth_headers):
    response = client.post(
        "/api/v1/admin/customers",
        headers={**auth_headers, "Origin": "https://evil.example"},
        json=CUSTOMER_PAYLOAD,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Origem não permitida"


def test_request_with_a_malformed_origin_is_rejected(client, auth_headers):
    response = client.post(
        "/api/v1/admin/customers",
        headers={**auth_headers, "Origin": "not-a-url"},
        json=CUSTOMER_PAYLOAD,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Origem não permitida"


def test_state_changing_request_without_origin_or_referer_is_rejected(
    client, auth_headers
):
    headers = {key: value for key, value in auth_headers.items() if key != "Origin"}

    response = client.post(
        "/api/v1/admin/customers",
        headers=headers,
        json=CUSTOMER_PAYLOAD,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Origem não permitida"


def test_state_changing_request_accepts_a_configured_referer(
    client, auth_headers
):
    headers = {
        key: value for key, value in auth_headers.items() if key != "Origin"
    }
    headers["Referer"] = "http://testserver/admin/customers"

    response = client.post(
        "/api/v1/admin/customers",
        headers=headers,
        json=CUSTOMER_PAYLOAD,
    )

    assert response.status_code == 201


def test_state_changing_request_rejects_a_malformed_referer(client, auth_headers):
    headers = {
        key: value for key, value in auth_headers.items() if key != "Origin"
    }
    headers["Referer"] = "not-a-url"

    response = client.post(
        "/api/v1/admin/customers",
        headers=headers,
        json=CUSTOMER_PAYLOAD,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Origem não permitida"


def test_request_from_the_apps_own_origin_is_allowed(client, auth_headers):
    """The legacy panel is served by this app, so its Origin is same-origin.

    Browsers attach Origin to same-origin POSTs, and the configured CORS list
    only names the Angular dev server - matching the request's own origin is
    what keeps the bundled panel working.
    """
    response = client.post(
        "/api/v1/admin/customers",
        headers={**auth_headers, "Origin": "http://testserver"},
        json=CUSTOMER_PAYLOAD,
    )

    assert response.status_code == 201


def test_configured_cors_origin_is_allowed(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "cors_allowed_origins", "https://painel.example")

    response = client.post(
        "/api/v1/admin/customers",
        headers={**auth_headers, "Origin": "https://painel.example"},
        json=CUSTOMER_PAYLOAD,
    )

    assert response.status_code == 201


def test_refresh_requires_a_csrf_header(client):
    login(client)

    assert client.post("/api/v1/auth/refresh").status_code == 403


# ------------------------------------------------------------------- sessions


def test_unauthenticated_request_is_rejected(client):
    assert client.get("/api/v1/admin/customers").status_code == 401


def test_refresh_rotates_the_session_and_keeps_the_caller_logged_in(client):
    headers = login(client)
    first_refresh = client.cookies.get(REFRESH_COOKIE)

    refreshed = client.post("/api/v1/auth/refresh", headers=headers)

    assert refreshed.status_code == 200
    assert refreshed.json()["username"] == "admin"
    assert client.cookies.get(REFRESH_COOKIE) != first_refresh
    assert client.get("/api/v1/admin/me").status_code == 200


def test_replaying_a_rotated_refresh_token_revokes_the_family(client):
    """A stale bearer token is treated as reuse, even during a client race."""
    headers = login(client)
    stale_refresh = client.cookies.get(REFRESH_COOKIE)

    first = client.post("/api/v1/auth/refresh", headers=headers)
    assert first.status_code == 200

    client.cookies.set(REFRESH_COOKIE, stale_refresh, path="/api/v1/auth")
    replay = client.post("/api/v1/auth/refresh", headers=csrf_headers(client))

    assert replay.status_code == 401
    assert client.get("/api/v1/admin/me").status_code == 401


def test_replaying_an_old_refresh_token_kills_the_family(client):
    headers = login(client)
    stale_refresh = client.cookies.get(REFRESH_COOKIE)

    rotated = client.post("/api/v1/auth/refresh", headers=headers)
    assert rotated.status_code == 200
    current_refresh = client.cookies.get(REFRESH_COOKIE)
    current_headers = csrf_headers(client)

    client.cookies.set(REFRESH_COOKIE, stale_refresh, path="/api/v1/auth")
    replay = client.post("/api/v1/auth/refresh", headers=current_headers)
    assert replay.status_code == 401

    # Revocation has to be committed even though the request failed, so the
    # token the attacker did not have is dead too.
    client.cookies.set(REFRESH_COOKIE, current_refresh, path="/api/v1/auth")
    assert (
        client.post("/api/v1/auth/refresh", headers=current_headers).status_code == 401
    )


def test_logout_revokes_the_access_token_not_just_the_cookie(client):
    headers = login(client)
    access = client.cookies.get(ACCESS_COOKIE)

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200

    # Put the captured access token back: the session behind it is gone.
    client.cookies.set(ACCESS_COOKIE, access, path=ACCESS_COOKIE_PATH)
    assert client.get("/api/v1/admin/me").status_code == 401


def test_refresh_after_logout_is_rejected(client):
    headers = login(client)
    refresh_token = client.cookies.get(REFRESH_COOKIE)

    client.post("/api/v1/auth/logout", headers=headers)

    client.cookies.set(REFRESH_COOKIE, refresh_token, path="/api/v1/auth")
    client.cookies.set(CSRF_COOKIE, "csrf-value", path="/")
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": "csrf-value", "Origin": "http://testserver"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------- roles


def _approved_service_order(client, auth_headers, captured_emails) -> int:
    customer = client.post(
        "/api/v1/admin/customers", headers=auth_headers, json=CUSTOMER_PAYLOAD
    ).json()
    vehicle = client.post(
        "/api/v1/admin/vehicles",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "plate": "ROL1A23",
            "state": "SP",
            "city": "São Paulo",
            "color": "Prata",
            "brand": "Fiat",
            "model": "Uno",
            "year": 2020,
        },
    ).json()
    service = client.post(
        "/api/v1/admin/services",
        headers=auth_headers,
        json={"name": "Revisão", "base_price": 100.0, "estimated_hours": 1.0},
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
        f"/api/v1/admin/budgets/{budget['id']}/send-email", headers=auth_headers
    )
    client.post(
        "/api/v1/public/budgets/decisions",
        json={"token": captured_emails.approval_token(), "decision": "approve"},
    )
    orders = client.get("/api/v1/admin/service-orders", headers=auth_headers).json()
    return orders["items"][0]["id"]


def test_status_override_is_refused_for_an_operator(
    client, auth_headers, captured_emails, second_client
):
    os_id = _approved_service_order(client, auth_headers, captured_emails)
    operator_headers = login(second_client, OPERATOR_CREDENTIALS)

    response = second_client.patch(
        f"/api/v1/admin/service-orders/{os_id}/status-override",
        headers=operator_headers,
        json={"status": "Em diagnóstico", "reason": "Tentativa indevida"},
    )

    assert response.status_code == 403


def test_status_override_is_allowed_for_an_admin(client, auth_headers, captured_emails):
    os_id = _approved_service_order(client, auth_headers, captured_emails)

    response = client.patch(
        f"/api/v1/admin/service-orders/{os_id}/status-override",
        headers=auth_headers,
        json={"status": "Em diagnóstico", "reason": "Correção administrativa"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Em diagnóstico"


def test_operator_can_still_use_the_ordinary_endpoints(second_client):
    operator_headers = login(second_client, OPERATOR_CREDENTIALS)

    assert second_client.get("/api/v1/admin/customers").status_code == 200
    assert (
        second_client.post(
            "/api/v1/admin/customers", headers=operator_headers, json=CUSTOMER_PAYLOAD
        ).status_code
        == 201
    )


# ---------------------------------------------------------------- rate limiting


def test_repeated_failed_logins_are_throttled(client, monkeypatch):
    monkeypatch.setattr(login_rate_limiter, "max_attempts", 3)

    for _ in range(3):
        failed = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert failed.status_code == 401

    # Correct credentials are refused too: the lockout is on the account.
    locked = client.post("/api/v1/auth/login", json=ADMIN_CREDENTIALS)
    assert locked.status_code == 429
    assert locked.headers["retry-after"]


@pytest.mark.parametrize(
    ("route", "path", "payload"),
    [
        (
            "service_order_tracking",
            "/api/v1/public/service-orders/track",
            {"token": "unknown-tracking-token"},
        ),
        (
            "budget_decision",
            "/api/v1/public/budgets/decisions",
            {"token": "unknown-approval-token", "decision": "approve"},
        ),
        (
            "customer_lookup",
            "/api/v1/customers/lookup",
            {"document": "52998224725", "email": "unknown@test.com"},
        ),
    ],
)
def test_public_routes_return_retry_after_when_rate_limit_is_exceeded(
    client, monkeypatch, route, path, payload
):
    monkeypatch.setattr(
        rate_limit,
        "PUBLIC_RATE_LIMIT_POLICIES",
        {route: RateLimitPolicy(max_requests=2, window_seconds=60)},
    )

    first = client.post(path, json=payload)
    second = client.post(path, json=payload)
    limited = client.post(path, json=payload)

    assert first.status_code != 429
    assert second.status_code != 429
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


def test_a_successful_login_clears_the_failure_counter(client, monkeypatch):
    monkeypatch.setattr(login_rate_limiter, "max_attempts", 3)

    client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert client.post("/api/v1/auth/login", json=ADMIN_CREDENTIALS).status_code == 200

    client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert client.post("/api/v1/auth/login", json=ADMIN_CREDENTIALS).status_code == 200


# ------------------------------------------------------ public approval tokens


def test_public_approval_token_is_single_use(client, auth_headers, captured_emails):
    _approved_service_order(client, auth_headers, captured_emails)
    token = captured_emails.approval_token()

    replay = client.post(
        "/api/v1/public/budgets/decisions",
        json={"token": token, "decision": "approve"},
    )
    assert replay.status_code == 200
    assert replay.json()["already_processed"] is True

    # The consumed token cannot be turned into the opposite decision.
    flipped = client.post(
        "/api/v1/public/budgets/decisions",
        json={"token": token, "decision": "reject"},
    )
    assert flipped.status_code == 422


def test_public_decision_endpoint_rejects_an_unknown_token(client):
    response = client.post(
        "/api/v1/public/budgets/decisions",
        json={"token": "not-a-real-token", "decision": "approve"},
    )

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


# ----------------------------------------------------------- security headers


def test_responses_carry_a_content_security_policy(client):
    response = client.get("/api/v1/admin/customers")

    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["x-content-type-options"] == "nosniff"


def test_api_docs_are_exempt_from_the_csp(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
