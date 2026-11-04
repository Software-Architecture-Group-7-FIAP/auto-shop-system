import json
import logging
from contextlib import contextmanager
from uuid import UUID

from fastapi.testclient import TestClient

from src.infrastructure.observability.json_logging import JsonLogFormatter
from src.main import app


@contextmanager
def _capture_logs(logger_name: str):
    stream_records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            stream_records.append(JsonLogFormatter("development").format(record))

    handler = _Capture()
    logger = logging.getLogger(logger_name)
    previous_level = logger.level
    previous_disabled = logger.disabled
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        yield stream_records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.disabled = previous_disabled


def test_health_echoes_correlation_id_and_stays_quiet(client):
    with _capture_logs("src.http") as records:
        response = client.get("/health/live", headers={"X-Correlation-ID": "probe-1"})

    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "probe-1"
    assert response.headers["x-request-id"] == "probe-1"
    payloads = [json.loads(line) for line in records]
    assert all(item.get("path") != "/health/live" for item in payloads)


def test_request_id_is_used_when_correlation_header_is_absent(client):
    response = client.get("/health/live", headers={"X-Request-ID": "legacy-id"})

    assert response.headers["x-correlation-id"] == "legacy-id"
    assert response.headers["x-request-id"] == "legacy-id"


def test_correlation_id_wins_over_request_id(client):
    response = client.get(
        "/health/live",
        headers={"X-Correlation-ID": "chain-id", "X-Request-ID": "legacy-id"},
    )

    assert response.headers["x-correlation-id"] == "chain-id"
    assert response.headers["x-request-id"] == "chain-id"


def test_unsafe_correlation_header_is_replaced(client):
    response = client.get("/health/live", headers={"X-Correlation-ID": "bad\r\ninjected"})

    generated = response.headers["x-correlation-id"]
    assert generated != "bad\r\ninjected"
    UUID(generated)


def test_access_log_is_json_with_correlation_id(client):
    with _capture_logs("src.http") as records:
        response = client.get("/", headers={"X-Correlation-ID": "home-1"})

    assert response.status_code == 200
    payloads = [json.loads(line) for line in records]
    access = next(item for item in payloads if item.get("event") == "http_request")
    assert access["message"] == "request completed"
    assert access["level"] == "INFO"
    assert access["service"] == "auto-shop-api"
    assert access["environment"] == "development"
    assert access["correlation_id"] == "home-1"
    assert access["http_method"] == "GET"
    assert access["path"] == "/"
    assert access["status_code"] == 200
    assert isinstance(access["duration_ms"], float)
    assert access["timestamp"].endswith("Z")


def test_unhandled_error_returns_correlation_headers(client, auth_headers, monkeypatch):
    class BoomService:
        def get_by_id(self, service_order_id: int):
            raise RuntimeError("simulated failure")

    monkeypatch.setattr(
        "src.api.routers.service_orders.compose_service_order_service",
        lambda db: BoomService(),
    )

    strict_client = TestClient(app, raise_server_exceptions=False)
    strict_client.cookies.update(client.cookies)
    response = strict_client.get(
        "/api/v1/admin/service-orders/1",
        headers={**auth_headers, "X-Correlation-ID": "err-trace-1"},
    )

    assert response.status_code == 500
    assert response.headers["x-correlation-id"] == "err-trace-1"
    assert response.headers["x-request-id"] == "err-trace-1"


def test_missing_service_order_log_carries_correlation_and_order_id(client, auth_headers):
    with _capture_logs("src.domain.errors") as records:
        response = client.get(
            "/api/v1/admin/service-orders/404",
            headers={**auth_headers, "X-Correlation-ID": "os-404"},
        )

    assert response.status_code == 404
    assert response.headers["x-correlation-id"] == "os-404"
    payloads = [json.loads(line) for line in records]
    domain = next(item for item in payloads if item.get("event") == "domain_error")
    assert domain["correlation_id"] == "os-404"
    assert domain["service_order_id"] == 404
    assert domain["error_code"] == "not_found"
    assert domain["service"] == "auto-shop-api"


def test_access_log_uses_route_template_instead_of_path_parameters(client, auth_headers):
    with _capture_logs("src.http") as records:
        response = client.get(
            "/api/v1/admin/service-orders/404",
            headers={**auth_headers, "X-Correlation-ID": "route-template"},
        )

    assert response.status_code == 404
    payloads = [json.loads(line) for line in records]
    access = next(item for item in payloads if item.get("event") == "http_request")
    assert access["path"] == "/api/v1/admin/service-orders/{service_order_id}"
    assert "404" not in access["path"]
