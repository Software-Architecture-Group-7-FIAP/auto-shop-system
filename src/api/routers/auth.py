import secrets

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from src.api.auth_cookies import CSRF_COOKIE, REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from src.api.composition.auth import compose_auth_service, compose_refresh_session_service
from src.api.csrf import enforce_csrf
from src.api.dependencies import get_current_user
from src.api.rate_limit import (
    enforce_login_rate_limit,
    login_rate_limiter,
    login_throttle_keys,
)
from src.api.schemas import LoginRequest, SessionResponse
from src.domain.auth.entity import UserRole
from src.domain.exceptions import DomainError, UnauthorizedError
from src.infrastructure.database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=SessionResponse)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    throttle_keys = login_throttle_keys(request, data.username)
    enforce_login_rate_limit(throttle_keys)

    service = compose_auth_service(db)
    try:
        user = service.authenticate(data.username, data.password)
    except DomainError:
        login_rate_limiter.register_failure(throttle_keys)
        raise

    login_rate_limiter.register_success(throttle_keys)
    session = compose_refresh_session_service(db).issue(user.id or 0)
    access_token = service.issue_access_token(user, session.session_id)
    csrf_token = secrets.token_urlsafe(32)
    db.commit()
    set_auth_cookies(response, access_token, session.refresh_token, csrf_token)
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(username=user.username, role=user.role)


@router.post("/refresh", response_model=SessionResponse)
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    csrf_token: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    db: Session = Depends(get_db),
):
    enforce_csrf(request, csrf_token)
    if not refresh_token:
        raise UnauthorizedError("Sessão inválida")
    sessions = compose_refresh_session_service(db)
    try:
        current, issued = sessions.rotate(refresh_token)
    except UnauthorizedError:
        # Reuse detection revokes the whole family; that revocation must
        # survive the failed request, so commit before propagating.
        db.commit()
        clear_auth_cookies(response)
        raise
    auth = compose_auth_service(db)
    user = auth.users.get_by_id(current.user_id)
    if not user or not user.is_active:
        sessions.revoke_family(current.family_id)
        db.commit()
        clear_auth_cookies(response)
        raise UnauthorizedError("Usuário inválido")
    access_token = auth.issue_access_token(user, issued.session_id)
    csrf_token = secrets.token_urlsafe(32)
    db.commit()
    set_auth_cookies(response, access_token, issued.refresh_token, csrf_token)
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(username=user.username, role=user.role)


@router.post("/logout", response_model=SessionResponse)
def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    csrf_token: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    db: Session = Depends(get_db),
):
    if refresh_token:
        enforce_csrf(request, csrf_token)
        compose_refresh_session_service(db).revoke_family_for_token(refresh_token)
        db.commit()
    clear_auth_cookies(response)
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(username="", role=UserRole.OPERATOR)


@router.get("/me", response_model=SessionResponse)
def me(current_user=Depends(get_current_user)):
    return SessionResponse(username=current_user.username, role=current_user.role)
