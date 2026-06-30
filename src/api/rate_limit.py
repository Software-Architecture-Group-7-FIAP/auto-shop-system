import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from src.config import settings

_requests: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(bucket: str, max_requests: int | str) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        client = request.client.host if request.client else "unknown"
        key = f"{bucket}:{client}"
        now = time.monotonic()
        window_start = now - settings.rate_limit_window_seconds
        entries = _requests[key]
        while entries and entries[0] < window_start:
            entries.popleft()
        request_limit = (
            getattr(settings, max_requests) if isinstance(max_requests, str) else max_requests
        )
        if len(entries) >= request_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas requisições. Tente novamente mais tarde.",
            )
        entries.append(now)

    return dependency


def clear_rate_limits() -> None:
    _requests.clear()
