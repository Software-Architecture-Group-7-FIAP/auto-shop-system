from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.api.composition.auth import compose_auth_service
from src.domain.auth.entity import User
from src.domain.exceptions import DomainError, UnauthorizedError
from src.infrastructure.database import get_db

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    try:
        return compose_auth_service(db).get_current_user(credentials.credentials)
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        )


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
