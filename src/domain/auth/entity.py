from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"


@dataclass
class User:
    id: int | None
    username: str
    email: str
    hashed_password: str
    is_active: bool = True
    role: UserRole = UserRole.OPERATOR
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        username: str,
        email: str,
        hashed_password: str,
        role: UserRole = UserRole.OPERATOR,
    ) -> "User":
        return cls(
            id=None,
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            role=role,
        )
