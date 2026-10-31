import json
import logging

import pytest

from src.api.correlation import CorrelationMiddleware
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.observability.context import correlation_id_var, service_order_id_var
from src.infrastructure.observability.json_logging import JsonLogFormatter, log_domain_error
from src.infrastructure.observability.redaction import redact


@pytest.mark.asyncio
async def test_middleware_stores_correlation_id_on_request_state():
    seen: dict[str, str] = {}

    async def app(scope, receive, send):
        seen["correlation_id"] = scope["state"]["correlation_id"]
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health/live",
        "headers": [(b"x-request-id", b"legacy-id")],
        "query_string": b"",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        return None

    await CorrelationMiddleware(app)(scope, receive, send)
    assert seen["correlation_id"] == "legacy-id"


def test_redact_strips_documents_tokens_and_secrets():
    raw = (
        "cpf 529.982.247-25 cnpj 11.222.333/0001-81 "
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.signature "
        "password=super-secret"
    )

    cleaned = redact(raw)

    assert "529.982.247-25" not in cleaned
    assert "11.222.333/0001-81" not in cleaned
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in cleaned
    assert "super-secret" not in cleaned
    assert "password=[REDACTED]" in cleaned
    assert "Bearer [REDACTED]" in cleaned


def test_json_formatter_emits_required_fields_and_correlation_id():
    formatter = JsonLogFormatter("staging")
    token = correlation_id_var.set("chain-1")
    order_token = service_order_id_var.set(42)
    try:
        record = logging.LogRecord(
            name="src.http",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="request completed",
            args=(),
            exc_info=None,
        )
        record.event = "http_request"
        record.http_method = "GET"
        record.path = "/api/v1/admin/service-orders/42"
        record.status_code = 200
        record.duration_ms = 3.5
        payload = json.loads(formatter.format(record))
    finally:
        correlation_id_var.reset(token)
        service_order_id_var.reset(order_token)

    assert payload["timestamp"].endswith("Z")
    assert payload["level"] == "INFO"
    assert payload["message"] == "request completed"
    assert payload["service"] == "auto-shop-api"
    assert payload["environment"] == "staging"
    assert payload["correlation_id"] == "chain-1"
    assert payload["service_order_id"] == 42
    assert payload["duration_ms"] == 3.5


def test_domain_error_on_service_order_uses_processing_failed_event():
    formatter = JsonLogFormatter("test")
    logger = logging.getLogger("src.domain.errors")
    logger.setLevel(logging.INFO)
    payloads: list[dict] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            payloads.append(json.loads(formatter.format(record)))

    capture = _Capture()
    logger.addHandler(capture)
    correlation = correlation_id_var.set("chain-os")
    order = service_order_id_var.set(7)
    try:
        log_domain_error(ValidationError("estoque insuficiente para o cpf 529.982.247-25"))
        log_domain_error(NotFoundError("OS não encontrada"))
    finally:
        correlation_id_var.reset(correlation)
        service_order_id_var.reset(order)
        logger.removeHandler(capture)

    failed, missing = payloads
    assert failed["event"] == "service_order_processing_failed"
    assert failed["error_code"] == "validation_error"
    assert failed["error_type"] == "ValidationError"
    assert failed["correlation_id"] == "chain-os"
    assert failed["service_order_id"] == 7
    assert "529.982.247-25" not in failed["message"]
    assert missing["event"] == "domain_error"
    assert missing["level"] == "INFO"
