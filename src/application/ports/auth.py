from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        ...

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        ...


class AccessTokenIssuer(Protocol):
    def create_access_token(self, subject: str, session_id: str | None = None) -> str:
        ...


class AccessTokenDecoder(Protocol):
    def decode_token(self, token: str) -> str:
        ...

    def decode_claims(self, token: str) -> dict:
        ...


class RefreshSessionStore(Protocol):
    """Rotating, revocable refresh sessions backing the cookie login."""

    def issue(self, user_id: int, family_id: str | None = None):
        ...

    def rotate(self, raw_token: str):
        ...

    def revoke_family(self, family_id: str) -> None:
        ...

    def revoke_family_for_token(self, raw_token: str) -> None:
        ...

    def is_active(self, session_id: str) -> bool:
        ...

    def belongs_to_user(self, session_id: str, user_id: int | None) -> bool:
        ...
