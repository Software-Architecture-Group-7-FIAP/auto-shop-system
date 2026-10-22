import json
import logging
from datetime import datetime, timezone

from src.domain.exceptions import DomainError
from src.infrastructure.observability.context import correlation_id_var, service_order_id_var
from src.infrastructure.observability.redaction import redact

SERVICE_NAME = "auto-shop-api"
_STACK_LIMIT = 4000
_LOG_FIELDS = (
    "event",
    "error_code",
    "error_type",
    "http_method",
    "path",
    "status_code",
    "duration_ms",
)


class JsonLogFormatter(logging.Formatter):
    def __init__(self, environment: str, service: str = SERVICE_NAME) -> None:
        super().__init__()
        self._environment = environment
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "message": redact(record.getMessage()),
            "service": self._service,
            "environment": self._environment,
            "logger": record.name,
            "correlation_id": correlation_id_var.get(),
        }
        service_order_id = getattr(record, "service_order_id", None)
        if service_order_id is None:
            service_order_id = service_order_id_var.get()
        if service_order_id is not None:
            payload["service_order_id"] = service_order_id
        for field in _LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
            stack = redact(self.formatException(record.exc_info))
            payload["stack_trace"] = stack[:_STACK_LIMIT]
        return json.dumps(payload, ensure_ascii=False)


_configured = False


def configure_json_logging(environment: str) -> None:
    global _configured
    if _configured:
        return
    app_logger = logging.getLogger("src")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    app_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter(environment))
    app_logger.addHandler(handler)
    _configured = True


def log_domain_error(exc: DomainError) -> None:
    order_id = service_order_id_var.get()
    event = "domain_error"
    if order_id is not None and exc.code != "not_found":
        event = "service_order_processing_failed"
    level = logging.INFO if exc.code == "not_found" else logging.WARNING
    logging.getLogger("src.domain.errors").log(
        level,
        exc.message,
        extra={
            "event": event,
            "error_code": exc.code,
            "error_type": type(exc).__name__,
            "service_order_id": order_id,
        },
    )
