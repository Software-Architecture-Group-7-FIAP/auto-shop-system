from uuid import uuid4

from fastapi import Request

from src.infrastructure.observability.context import accept_correlation_id


def request_correlation_id(request: Request) -> str:
    """Return the middleware-bound id when present, else a safe header value or a new uuid."""
    state = getattr(request, "state", None)
    value = getattr(state, "correlation_id", None) if state is not None else None
    if isinstance(value, str) and value:
        return value
    for header_name in ("x-correlation-id", "x-request-id"):
        accepted = accept_correlation_id(request.headers.get(header_name))
        if accepted:
            return accepted
    generated = str(uuid4())
    if state is not None:
        state.correlation_id = generated
    return generated
