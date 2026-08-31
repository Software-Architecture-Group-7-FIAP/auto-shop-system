from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt.exceptions import PyJWTError as JWTError

from src.config import settings
from src.domain.exceptions import UnauthorizedError

JWT_ALGORITHM = "HS256"


class BcryptPasswordHasher:
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


class JwtAccessTokenService:
    def _secret(self) -> str:
        access_secret = getattr(settings, "access_token_secret_value", None)
        if callable(access_secret):
            return access_secret()
        return settings.jwt_secret()

    def create_access_token(self, subject: str, session_id: str | None = None) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        payload = {"sub": subject, "exp": expire}
        if session_id:
            payload["sid"] = session_id
        return jwt.encode(payload, self._secret(), algorithm=JWT_ALGORITHM)

    def decode_token(self, token: str) -> str:
        try:
            payload = jwt.decode(
                token,
                self._secret(),
                algorithms=[JWT_ALGORITHM],
                options={"require": ["exp"]},
            )
            username: str | None = payload.get("sub")
            if username is None:
                raise UnauthorizedError("Token inválido")
            return username
        except JWTError as exc:
            raise UnauthorizedError("Token inválido") from exc

    def decode_claims(self, token: str) -> dict:
        try:
            return jwt.decode(
                token,
                self._secret(),
                algorithms=[JWT_ALGORITHM],
                options={"require": ["exp"]},
            )
        except JWTError as exc:
            raise UnauthorizedError("Token inválido") from exc
