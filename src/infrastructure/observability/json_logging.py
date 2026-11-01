import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timezone

from src.domain.exceptions import DomainError
from src.infrastructure.observability.context import correlation_id_var, service_order_id_var
from src.infrastructure.observability.redaction import redact

SERVICE_NAME = "auto-shop-api"
_LINKING_FIELDS = frozenset({"trace.id", "span.id"})
_STACK_LIMIT = 4000
_LOG_FIELDS = (
    "event",
    "event_id",
    "event_version",
    "occurred_at",
    "error_code",
    "error_type",
    "failure_type",
    "subsystem",
    "http_method",
    "path",
    "status_code",
    "status",
    "to_status",
    "transition_type",
    "duration_ms",
    "duration_unit",
)


def _new_relic_linking_metadata() -> Mapping[str, str]:
    try:
        from newrelic.agent import get_linking_metadata

        return get_linking_metadata()
    except (ImportError, RuntimeError):
        return {}


class JsonLogFormatter(logging.Formatter):
    def __init__(
        self,
        environment: str,
        service: str = SERVICE_NAME,
        version: str = "unknown",
        linking_metadata_provider: Callable[[], Mapping[str, str]] = _new_relic_linking_metadata,
    ) -> None:
        super().__init__()
        self._environment = environment
        self._service = service
        self._version = version
        self._linking_metadata_provider = linking_metadata_provider

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "message": redact(record.getMessage()),
            "service": self._service,
            "environment": self._environment,
            "version": self._version,
            "logger": record.name,
        }
        is_business_event = getattr(record, "business_event", False) is True
        correlation_id = correlation_id_var.get()
        if correlation_id is not None and not is_business_event:
            payload["correlation_id"] = correlation_id
        service_order_id = getattr(record, "service_order_id", None)
        if service_order_id is None and not is_business_event:
            service_order_id = service_order_id_var.get()
        if service_order_id is not None:
            payload["service_order_id"] = service_order_id
        for field in _LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = redact(value) if isinstance(value, str) else value
        linking_metadata = self._linking_metadata_provider()
        for field in _LINKING_FIELDS:
            value = linking_metadata.get(field)
            if value:
                payload[field] = redact(str(value))
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
            stack = redact(self.formatException(record.exc_info))
            payload["stack_trace"] = stack[:_STACK_LIMIT]
        return json.dumps(payload, ensure_ascii=False)


def _record_new_relic_log(
    message: str,
    level: str,
    attributes: dict[str, object],
) -> None:
    from newrelic.agent import record_log_event

    record_log_event(message, level, attributes=attributes)


class NewRelicJsonLogHandler(logging.Handler):
    """Forward only the already-sanitized application JSON to New Relic."""

    def __init__(
        self,
        formatter: JsonLogFormatter,
        recorder: Callable[[str, str, dict[str, object]], None] = _record_new_relic_log,
    ) -> None:
        super().__init__()
        self.setFormatter(formatter)
        self._recorder = recorder

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.loads(self.format(record))
            self._recorder(payload["message"], record.levelname, payload)
        except Exception:
            # Fail closed: logging internals must never print the original,
            # potentially sensitive LogRecord when telemetry delivery fails.
            return


_configured = False


def configure_json_logging(environment: str, version: str = "unknown") -> None:
    global _configured
    if _configured:
        return
    app_logger = logging.getLogger("src")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    app_logger.handlers.clear()
    formatter = JsonLogFormatter(environment, version=version)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)
    if environment == "staging":
        app_logger.addHandler(NewRelicJsonLogHandler(formatter))
    _configured = True


def log_domain_error(exc: DomainError) -> None:
    order_id = service_order_id_var.get()
    event = "domain_error"
    if order_id is not None and exc.code != "not_found":
        event = "service_order_domain_rejection"
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
