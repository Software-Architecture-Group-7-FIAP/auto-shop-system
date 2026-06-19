from src.application.ports.auth import (
    AccessTokenDecoder,
    AccessTokenIssuer,
    PasswordHasher,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository
from src.domain.exceptions import DomainError, UnauthorizedError


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordHasher,
        tokens: AccessTokenIssuer,
        token_decoder: AccessTokenDecoder,
        uow: UnitOfWork,
    ):
        self.users = users
        self.passwords = passwords
        self.tokens = tokens
        self.token_decoder = token_decoder
        self.uow = uow

    def login(self, username: str, password: str) -> str:
        self.ensure_default_admin()
        user = self.users.get_by_username(username)
        if not user or not self.passwords.verify(password, user.hashed_password):
            raise DomainError("Credenciais inválidas", "unauthorized")
        return self.tokens.create_access_token(user.username)

    def get_current_user(self, token: str) -> User:
        username = self.token_decoder.decode_token(token)
        user = self.users.get_by_username(username)
        if not user or not user.is_active:
            raise UnauthorizedError("Usuário inválido")
        return user

    def ensure_default_admin(self) -> None:
        if self.users.get_by_username("admin"):
            return
        self.users.add(
            User.create(
                username="admin",
                email="admin@oficina.local",
                hashed_password=self.passwords.hash("admin123"),
            )
        )
        self.uow.commit()
