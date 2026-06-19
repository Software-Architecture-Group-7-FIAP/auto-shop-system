from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: int | None
    username: str
    email: str
    hashed_password: str
    is_active: bool = True
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        username: str,
        email: str,
        hashed_password: str,
    ) -> "User":
        return cls(
            id=None,
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
        )
