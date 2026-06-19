from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        ...

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        ...


class AccessTokenIssuer(Protocol):
    def create_access_token(self, subject: str) -> str:
        ...


class AccessTokenDecoder(Protocol):
    def decode_token(self, token: str) -> str:
        ...
