import hashlib
import hmac
import secrets

from src.config import settings


class HmacServiceOrderTrackingTokenService:
    def create_token(self) -> str:
        return secrets.token_urlsafe(32)

    def fingerprint(self, token: str) -> str:
        return hmac.new(
            settings.tracking_secret().encode(),
            token.encode(),
            hashlib.sha256,
        ).hexdigest()
