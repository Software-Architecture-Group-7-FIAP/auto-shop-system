from sqlalchemy.orm import Session

from src.domain.auth.entity import User
from src.infrastructure.database import UserModel


class SqlAlchemyUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, user: User) -> User:
        model = UserModel(
            username=user.username,
            email=user.email,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            role=user.role,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_username(self, username: str) -> User | None:
        model = self.db.query(UserModel).filter(UserModel.username == username).first()
        if not model:
            return None
        return self._to_domain(model)

    def get_by_id(self, user_id: int) -> User | None:
        model = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        return self._to_domain(model) if model else None

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            hashed_password=model.hashed_password,
            is_active=model.is_active,
            role=model.role,
            created_at=model.created_at,
        )
