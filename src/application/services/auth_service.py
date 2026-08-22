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

    def authenticate(self, username: str, password: str) -> User:
        user = self.users.get_by_username(username)
        if not user or not self.passwords.verify(password, user.hashed_password):
            raise DomainError("Credenciais inválidas", "unauthorized")
        if not user.is_active:
            raise UnauthorizedError("Usuário inválido")
        return user

    def login(self, username: str, password: str, session_id: str) -> str:
        """Authenticate and mint an access token bound to a refresh session.

        ``session_id`` is mandatory: ``get_current_user`` rejects any token
        without a live ``sid`` claim, so a session-less token could never
        authenticate anything.
        """
        user = self.authenticate(username, password)
        return self.issue_access_token(user, session_id)

    def issue_access_token(self, user: User, session_id: str) -> str:
        return self.tokens.create_access_token(user.username, session_id)

    def get_current_user(self, token: str) -> User:
        username = self.token_decoder.decode_token(token)
        user = self.users.get_by_username(username)
        if not user or not user.is_active:
            raise UnauthorizedError("Usuário inválido")
        return user
