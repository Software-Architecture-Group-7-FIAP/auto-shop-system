from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.api.auth_cookies import ACCESS_COOKIE, CSRF_COOKIE
from src.api.composition.auth import compose_auth_service, compose_refresh_session_service
from src.api.csrf import enforce_csrf
from src.domain.auth.entity import User
from src.domain.auth.entity import UserRole
from src.domain.exceptions import DomainError, UnauthorizedError
from src.infrastructure.database import get_db


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    csrf_token: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    bearer_token = _extract_bearer_token(authorization)
    token = bearer_token or access_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária",
        )
    if bearer_token is None:
        enforce_csrf(request, csrf_token)
    try:
        auth = compose_auth_service(db)
        claims = auth.token_decoder.decode_claims(token)
        session_id = claims.get("sid")
        user = auth.get_current_user(token)
        sessions = compose_refresh_session_service(db)
        if not isinstance(session_id, str) or not sessions.belongs_to_user(session_id, user.id):
            raise UnauthorizedError("Sessão inválida")
        return user
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        )


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem executar esta operação",
        )
    return current_user


def domain_error_handler(exc: DomainError) -> HTTPException:
    status_map = {
        "not_found": status.HTTP_404_NOT_FOUND,
        "validation_error": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "conflict_error": status.HTTP_409_CONFLICT,
        "unauthorized": status.HTTP_401_UNAUTHORIZED,
        "forbidden": status.HTTP_403_FORBIDDEN,
        "service_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    }
    return HTTPException(
        status_code=status_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.message,
    )
