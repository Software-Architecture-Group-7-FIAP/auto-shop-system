from sqlalchemy.orm import Session

from src.application.ports.auth import RefreshSessionStore
from src.application.services.auth_service import AuthService
from src.infrastructure.auth.jwt import BcryptPasswordHasher, JwtAccessTokenService
from src.infrastructure.auth.sessions import RefreshSessionService
from src.infrastructure.persistence.auth_repository import SqlAlchemyUserRepository
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_auth_service(db: Session) -> AuthService:
    token_service = JwtAccessTokenService()
    return AuthService(
        users=SqlAlchemyUserRepository(db),
        passwords=BcryptPasswordHasher(),
        tokens=token_service,
        token_decoder=token_service,
        uow=SqlAlchemyUnitOfWork(db),
    )


def compose_refresh_session_service(db: Session) -> RefreshSessionStore:
    return RefreshSessionService(db)
