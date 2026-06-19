from dataclasses import replace

import pytest

from src.application.services.auth_service import AuthService
from src.domain.auth.entity import User
from src.domain.exceptions import DomainError, UnauthorizedError


class InMemoryUserRepository:
    def __init__(self, users: list[User] | None = None):
        self.users = {user.username: user for user in users or []}
        self.next_id = 1

    def add(self, user: User) -> User:
        created = replace(user, id=self.next_id)
        self.users[created.username] = created
        self.next_id += 1
        return created

    def get_by_username(self, username: str) -> User | None:
        return self.users.get(username)


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return hashed_password == self.hash(plain_password)


class FakeTokenService:
    def __init__(self):
        self.decoded_subject = "admin"

    def create_access_token(self, subject: str) -> str:
        return f"token:{subject}"

    def decode_token(self, token: str) -> str:
        if token == "invalid":
            raise UnauthorizedError("Token inválido")
        return self.decoded_subject


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def make_auth_service(
    users: InMemoryUserRepository | None = None,
    tokens: FakeTokenService | None = None,
    uow: FakeUnitOfWork | None = None,
) -> AuthService:
    token_service = tokens or FakeTokenService()
    return AuthService(
        users=users or InMemoryUserRepository(),
        passwords=FakePasswordHasher(),
        tokens=token_service,
        token_decoder=token_service,
        uow=uow or FakeUnitOfWork(),
    )


def test_auth_service_creates_default_admin_once():
    users = InMemoryUserRepository()
    uow = FakeUnitOfWork()
    service = make_auth_service(users=users, uow=uow)

    service.ensure_default_admin()
    service.ensure_default_admin()

    admin = users.get_by_username("admin")
    assert admin is not None
    assert admin.email == "admin@oficina.local"
    assert admin.hashed_password == "hashed:admin123"
    assert uow.commits == 1


def test_auth_service_login_returns_access_token():
    users = InMemoryUserRepository(
        [
            User(
                id=1,
                username="admin",
                email="admin@oficina.local",
                hashed_password="hashed:admin123",
            )
        ]
    )
    service = make_auth_service(users=users)

    token = service.login("admin", "admin123")

    assert token == "token:admin"


def test_auth_service_login_rejects_invalid_credentials():
    users = InMemoryUserRepository(
        [
            User(
                id=1,
                username="admin",
                email="admin@oficina.local",
                hashed_password="hashed:admin123",
            )
        ]
    )
    service = make_auth_service(users=users)

    with pytest.raises(DomainError, match="Credenciais inválidas"):
        service.login("admin", "wrong")


def test_auth_service_get_current_user_decodes_token_and_loads_active_user():
    users = InMemoryUserRepository(
        [
            User(
                id=1,
                username="admin",
                email="admin@oficina.local",
                hashed_password="hashed:admin123",
            )
        ]
    )
    service = make_auth_service(users=users)

    user = service.get_current_user("token:admin")

    assert user.username == "admin"


def test_auth_service_get_current_user_rejects_inactive_user():
    users = InMemoryUserRepository(
        [
            User(
                id=1,
                username="admin",
                email="admin@oficina.local",
                hashed_password="hashed:admin123",
                is_active=False,
            )
        ]
    )
    service = make_auth_service(users=users)

    with pytest.raises(UnauthorizedError, match="Usuário inválido"):
        service.get_current_user("token:admin")


def test_auth_service_get_current_user_propagates_invalid_token():
    service = make_auth_service()

    with pytest.raises(UnauthorizedError, match="Token inválido"):
        service.get_current_user("invalid")
