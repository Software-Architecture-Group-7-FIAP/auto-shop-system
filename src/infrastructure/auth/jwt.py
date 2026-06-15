from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.config import settings
from src.domain.exceptions import UnauthorizedError
from src.infrastructure.database import UserModel


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str | None = payload.get("sub")
        if username is None:
            raise UnauthorizedError("Token inválido")
        return username
    except JWTError as exc:
        raise UnauthorizedError("Token inválido") from exc


def authenticate_user(db: Session, username: str, password: str) -> UserModel | None:
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user and verify_password(password, user.hashed_password):
        return user
    return None


def ensure_default_admin(db: Session) -> None:
    if db.query(UserModel).filter(UserModel.username == "admin").first():
        return
    admin = UserModel(
        username="admin",
        email="admin@oficina.local",
        hashed_password=hash_password("admin123"),
    )
    db.add(admin)
    db.commit()
