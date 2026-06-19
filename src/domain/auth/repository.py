from typing import Protocol

from src.domain.auth.entity import User


class UserRepository(Protocol):
    def add(self, user: User) -> User:
        ...

    def get_by_username(self, username: str) -> User | None:
        ...
