from fastapi import Response

from src.config import settings


ACCESS_COOKIE = "oficina_access"
REFRESH_COOKIE = "oficina_refresh"
CSRF_COOKIE = "oficina_csrf"


def cookie_secure() -> bool:
    return settings.is_production_like()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    secure = cookie_secure()
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")
