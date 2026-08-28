from datetime import datetime, timezone
from pydantic import SecretStr

from src.config import settings
from src.infrastructure.auth.service_order_tracking import HmacServiceOrderTrackingTokenService
from src.infrastructure.auth.tokens import (
    approval_token_expires_at,
    approval_token_fingerprint,
    create_signed_approval_token,
)


def test_approval_token_fingerprint_is_not_the_bearer_token():
    token = create_signed_approval_token(42)

    assert approval_token_fingerprint(token) != token
    assert len(approval_token_fingerprint(token)) == 64


def test_approval_token_expiration_is_bound_to_signed_claim():
    token = create_signed_approval_token(42)

    expires_at = approval_token_expires_at(token)

    assert expires_at > datetime.now(timezone.utc).replace(tzinfo=None)


def test_tracking_fingerprint_uses_a_separate_configured_secret(monkeypatch):
    monkeypatch.setattr(settings, "tracking_token_secret", SecretStr("tracking-secret-for-test"))
    service = HmacServiceOrderTrackingTokenService()
    token = service.create_token()

    assert service.fingerprint(token) != token
    assert len(service.fingerprint(token)) == 64
