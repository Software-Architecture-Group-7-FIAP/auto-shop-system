import pytest

from src.domain.exceptions import ServiceUnavailableError
from src.infrastructure.email import service as email_service


@pytest.mark.asyncio
async def test_send_email_raises_service_unavailable_when_smtp_fails(monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)

    async def failing_send(*args, **kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(email_service.aiosmtplib, "send", failing_send)

    with pytest.raises(ServiceUnavailableError, match="Serviço de email indisponível"):
        await email_service.send_email(
            "customer@test.local",
            "Orçamento #1",
            "Body",
        )


@pytest.mark.asyncio
async def test_send_email_skips_delivery_in_tests(monkeypatch):
    monkeypatch.setenv("TESTING", "1")

    async def failing_send(*args, **kwargs):
        raise AssertionError("SMTP should not be called while TESTING=1")

    monkeypatch.setattr(email_service.aiosmtplib, "send", failing_send)

    await email_service.send_email(
        "customer@test.local",
        "Orçamento #1",
        "Body",
    )
