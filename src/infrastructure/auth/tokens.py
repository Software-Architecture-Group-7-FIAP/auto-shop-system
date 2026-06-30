import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from src.config import settings


def generate_approval_token(budget_id: int) -> str:
    token = secrets.token_urlsafe(32)
    return token


def create_signed_approval_token(budget_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.budget_approval_token_expire_hours
    )
    payload = {"budget_id": budget_id, "type": "budget_approval", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret(), algorithm=settings.algorithm)


def validate_approval_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret(), algorithms=[settings.algorithm])
        if payload.get("type") != "budget_approval":
            raise ValueError("Invalid token type")
        if "exp" not in payload:
            raise ValueError("Missing expiration")
        budget_id = payload.get("budget_id")
        if not isinstance(budget_id, int):
            raise ValueError("Invalid budget id")
        return budget_id
    except JWTError as exc:
        raise ValueError("Invalid approval token") from exc
