"""Double-submit CSRF enforcement for cookie-authenticated requests."""

import hmac
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status

from src.config import settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def request_origin(request: Request) -> str | None:
    """Return the origin the app itself is being served from for this request.

    ``Origin`` is set by the browser to the page's own origin, and ``Host`` is
    set by the browser to the target it is calling. A cross-site forgery from
    ``evil.com`` therefore carries ``Origin: https://evil.com`` while ``Host``
    still points at this app, so comparing the two is a sound same-origin
    check that does not need the deployment port to be configured anywhere.
    """
    if not request.url.scheme or not request.url.netloc:
        return None
    return f"{request.url.scheme}://{request.url.netloc}"


def is_allowed_origin(request: Request, origin: str) -> bool:
    parsed = urlparse(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        return False
    return origin == request_origin(request) or origin in settings.request_origins()


def referer_origin(referer: str) -> str | None:
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def enforce_csrf(request: Request, csrf_cookie: str | None) -> None:
    """Reject state-changing requests with a foreign origin or a bad CSRF token."""
    if request.method in SAFE_METHODS:
        return

    origin = request.headers.get("origin")
    if origin:
        allowed = is_allowed_origin(request, origin)
    else:
        referer = request.headers.get("referer")
        referer_value = referer_origin(referer) if referer else None
        allowed = referer_value is not None and is_allowed_origin(request, referer_value)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origem não permitida",
        )

    header_token = request.headers.get("x-csrf-token")
    if not csrf_cookie or not header_token or not hmac.compare_digest(csrf_cookie, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF inválido",
        )
