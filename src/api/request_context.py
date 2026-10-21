from uuid import UUID, uuid4

from fastapi import Request


def request_correlation_id(request: Request) -> str:
    """Accept UUID correlation identifiers only, so personal data cannot enter logs."""
    for header_name in ("x-correlation-id", "x-request-id"):
        candidate = request.headers.get(header_name)
        if not candidate:
            continue
        try:
            return str(UUID(candidate.strip()))
        except (AttributeError, ValueError):
            continue
    return str(uuid4())
