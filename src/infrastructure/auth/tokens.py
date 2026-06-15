import secrets

from jose import jwt

from src.config import settings


def generate_approval_token(budget_id: int) -> str:
    token = secrets.token_urlsafe(32)
    return token


def create_signed_approval_token(budget_id: int) -> str:
    payload = {"budget_id": budget_id, "type": "budget_approval"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_approval_token(token: str) -> int:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    if payload.get("type") != "budget_approval":
        raise ValueError("Invalid token type")
    return int(payload["budget_id"])
