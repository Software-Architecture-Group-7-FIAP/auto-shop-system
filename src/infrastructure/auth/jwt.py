from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from src.config import settings
from src.domain.exceptions import UnauthorizedError


class BcryptPasswordHasher:
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


class JwtAccessTokenService:
    def create_access_token(self, subject: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        payload = {"sub": subject, "exp": expire}
        return jwt.encode(payload, settings.jwt_secret(), algorithm=settings.algorithm)

    def decode_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, settings.jwt_secret(), algorithms=[settings.algorithm])
            username: str | None = payload.get("sub")
            if username is None:
                raise UnauthorizedError("Token inválido")
            return username
        except JWTError as exc:
            raise UnauthorizedError("Token inválido") from exc
