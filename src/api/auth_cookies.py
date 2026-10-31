from fastapi import Response

from src.config import settings


ACCESS_COOKIE = "oficina_access"
ACCESS_COOKIE_PATH = "/api/v1/admin"
REFRESH_COOKIE = "oficina_refresh"
CSRF_COOKIE = "oficina_csrf"


def cookie_secure() -> bool:
    return settings.is_production_like()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    secure = cookie_secure()
    # Remove the pre-hardening root-scoped access cookie before issuing the
    # restricted replacement. Without this, browsers may send two cookies
    # with the same name during the transition.
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path=ACCESS_COOKIE_PATH,
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
    # Remove both paths so sessions created before the path hardening do not
    # remain as broad root-scoped cookies in the browser.
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(ACCESS_COOKIE, path=ACCESS_COOKIE_PATH)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")
