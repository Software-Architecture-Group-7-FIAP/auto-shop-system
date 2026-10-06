import logging
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.infrastructure.observability.context import (
    accept_correlation_id,
    correlation_id_var,
    service_order_id_from_path,
    service_order_id_var,
)

logger = logging.getLogger("src.http")

QUIET_PATHS = frozenset({"/health", "/health/live", "/health/ready", "/favicon.ico"})


class CorrelationMiddleware:
    """Bind one id per request and emit a JSON access line.

    ``X-Correlation-ID`` wins. ``X-Request-ID`` is the fallback so the id
    already stored on service-order history stays the chain id. Health
    probes stay quiet so they do not flood the log stream.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        correlation_id = (
            accept_correlation_id(headers.get("x-correlation-id"))
            or accept_correlation_id(headers.get("x-request-id"))
            or str(uuid4())
        )
        path = scope.get("path", "")
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        correlation_token = correlation_id_var.set(correlation_id)
        order_token = service_order_id_var.set(service_order_id_from_path(path))
        started = time.perf_counter()
        status_code = 500

        async def send_with_correlation(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = list(message.get("headers", []))
                encoded = correlation_id.encode("ascii")
                response_headers.append((b"x-correlation-id", encoded))
                response_headers.append((b"x-request-id", encoded))
                message = {**message, "headers": response_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        except Exception:
            logger.exception(
                "unhandled exception",
                extra={"event": "unhandled_exception", "http_method": scope.get("method"), "path": path},
            )
            raise
        finally:
            if path not in QUIET_PATHS:
                logger.info(
                    "request completed",
                    extra={
                        "event": "http_request",
                        "http_method": scope.get("method"),
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
            correlation_id_var.reset(correlation_token)
            service_order_id_var.reset(order_token)


def request_correlation_id(request) -> str:
    value = getattr(request.state, "correlation_id", None)
    if isinstance(value, str) and value:
        return value
    generated = str(uuid4())
    request.state.correlation_id = generated
    return generated
