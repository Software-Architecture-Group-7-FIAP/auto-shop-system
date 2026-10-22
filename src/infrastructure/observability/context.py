import re
from contextvars import ContextVar

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
service_order_id_var: ContextVar[int | None] = ContextVar("service_order_id", default=None)

# Fits service_order_status_history.request_id (varchar 128) and blocks header injection.
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SERVICE_ORDER_PATH = re.compile(r"/service-orders/(\d+)(?:/|$)")


def accept_correlation_id(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if _SAFE_ID.fullmatch(candidate):
        return candidate
    return None


def service_order_id_from_path(path: str) -> int | None:
    match = _SERVICE_ORDER_PATH.search(path)
    if match is None:
        return None
    return int(match.group(1))
