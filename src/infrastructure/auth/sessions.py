from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from uuid import uuid4

from sqlalchemy.orm import Session

from src.config import settings
from src.domain.exceptions import UnauthorizedError
from src.infrastructure.database import RefreshSessionModel


def _as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


@dataclass(frozen=True)
class IssuedSession:
    session_id: str
    refresh_token: str
    expires_at: datetime


class RefreshSessionService:
    """Persistence adapter for rotating, revocable refresh sessions."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _pepper() -> str:
        pepper = getattr(settings, "refresh_token_pepper_value", None)
        return pepper() if callable(pepper) else settings.jwt_secret()

    @classmethod
    def fingerprint(cls, token: str) -> str:
        return hmac.new(
            cls._pepper().encode(), token.encode(), hashlib.sha256
        ).hexdigest()

    def issue(self, user_id: int, family_id: str | None = None) -> IssuedSession:
        raw_token = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.refresh_token_expire_days)
        session = RefreshSessionModel(
            id=str(uuid4()),
            user_id=user_id,
            token_hash=self.fingerprint(raw_token),
            family_id=family_id or str(uuid4()),
            expires_at=expires_at,
            created_at=now,
            last_used_at=now,
        )
        self.db.add(session)
        self.db.flush()
        return IssuedSession(session.id, raw_token, expires_at)

    def rotate(self, raw_token: str) -> tuple[RefreshSessionModel, IssuedSession]:
        current = (
            self.db.query(RefreshSessionModel)
            .filter(RefreshSessionModel.token_hash == self.fingerprint(raw_token))
            .with_for_update()
            .first()
        )
        if not current:
            raise UnauthorizedError("Sessão inválida")

        now = datetime.now(timezone.utc)
        if current.revoked_at is not None:
            # A rotated refresh token is a bearer credential that has already
            # been spent. Any replay is indistinguishable from token theft at
            # this boundary, so revoke the complete family before rejecting it.
            # Clients serialize refresh calls and retry once with the new
            # cookie; accepting a stale token would allow unbounded sibling
            # sessions to be minted by an attacker.
            self.revoke_family(current.family_id)
            raise UnauthorizedError("Sessão reutilizada")

        expires_at = _as_utc(current.expires_at)
        if expires_at <= now:
            current.revoked_at = now
            self.db.flush()
            raise UnauthorizedError("Sessão expirada")

        current.revoked_at = now
        current.last_used_at = now
        issued = self.issue(current.user_id, current.family_id)
        current.replaced_by_id = issued.session_id
        self.db.flush()
        return current, issued

    def revoke(self, raw_token: str) -> None:
        current = (
            self.db.query(RefreshSessionModel)
            .filter(RefreshSessionModel.token_hash == self.fingerprint(raw_token))
            .first()
        )
        if current and current.revoked_at is None:
            current.revoked_at = datetime.now(timezone.utc)
            self.db.flush()

    def revoke_family_for_token(self, raw_token: str) -> None:
        current = (
            self.db.query(RefreshSessionModel)
            .filter(RefreshSessionModel.token_hash == self.fingerprint(raw_token))
            .first()
        )
        if current:
            self.revoke_family(current.family_id)

    def revoke_family(self, family_id: str) -> None:
        now = datetime.now(timezone.utc)
        (
            self.db.query(RefreshSessionModel)
            .filter(
                RefreshSessionModel.family_id == family_id,
                RefreshSessionModel.revoked_at.is_(None),
            )
            .update({RefreshSessionModel.revoked_at: now}, synchronize_session=False)
        )
        self.db.flush()

    def is_active(self, session_id: str) -> bool:
        session = self.db.get(RefreshSessionModel, session_id)
        if not session or session.revoked_at is not None:
            return False
        return _as_utc(session.expires_at) > datetime.now(timezone.utc)

    def belongs_to_user(self, session_id: str, user_id: int | None) -> bool:
        if user_id is None:
            return False
        session = self.db.get(RefreshSessionModel, session_id)
        return bool(session and session.user_id == user_id and self.is_active(session_id))
