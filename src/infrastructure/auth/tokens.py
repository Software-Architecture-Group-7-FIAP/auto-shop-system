import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from src.config import settings


def create_signed_approval_token(budget_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.budget_approval_token_expire_hours
    )
    payload = {"budget_id": budget_id, "type": "budget_approval", "exp": expire}
    return jwt.encode(payload, settings.budget_approval_secret(), algorithm=settings.algorithm)


def approval_token_fingerprint(token: str) -> str:
    """Return a deterministic, non-reversible database lookup fingerprint."""

    return hmac.new(
        settings.budget_approval_secret().encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def approval_token_expires_at(token: str) -> datetime:
    """Read the expiry from a token whose signature is verified first."""
    try:
        payload = jwt.decode(
            token,
            settings.budget_approval_secret(),
            algorithms=[settings.algorithm],
        )
        expires = payload.get("exp")
        if not isinstance(expires, (int, float)):
            raise ValueError("Missing expiration")
        return datetime.fromtimestamp(expires, tz=timezone.utc).replace(tzinfo=None)
    except (JWTError, OSError, OverflowError, TypeError, ValueError) as exc:
        raise ValueError("Invalid approval token") from exc


def validate_approval_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.budget_approval_secret(),
            algorithms=[settings.algorithm],
        )
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
