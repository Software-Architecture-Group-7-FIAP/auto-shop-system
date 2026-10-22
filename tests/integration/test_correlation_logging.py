import json
import logging
from uuid import UUID

from src.infrastructure.observability.json_logging import JsonLogFormatter


def _capture_src_logs():
    stream_records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            stream_records.append(JsonLogFormatter("development").format(record))

    handler = _Capture()
    logger = logging.getLogger("src")
    logger.addHandler(handler)
    return logger, handler, stream_records


def test_health_echoes_correlation_id_and_stays_quiet(client):
    logger, handler, records = _capture_src_logs()
    try:
        response = client.get("/health/live", headers={"X-Correlation-ID": "probe-1"})
    finally:
        logger.removeHandler(handler)

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
    logger, handler, records = _capture_src_logs()
    try:
        response = client.get("/", headers={"X-Correlation-ID": "home-1"})
    finally:
        logger.removeHandler(handler)

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


def test_missing_service_order_log_carries_correlation_and_order_id(client, auth_headers):
    logger, handler, records = _capture_src_logs()
    try:
        response = client.get(
            "/api/v1/admin/service-orders/404",
            headers={**auth_headers, "X-Correlation-ID": "os-404"},
        )
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 404
    assert response.headers["x-correlation-id"] == "os-404"
    payloads = [json.loads(line) for line in records]
    domain = next(item for item in payloads if item.get("event") == "domain_error")
    assert domain["correlation_id"] == "os-404"
    assert domain["service_order_id"] == 404
    assert domain["error_code"] == "not_found"
    assert domain["service"] == "auto-shop-api"
