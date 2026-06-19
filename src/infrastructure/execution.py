from datetime import UTC, datetime

from src.config import settings
from src.infrastructure.email.service import send_email


class SystemExecutionClock:
    def now(self) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)


class SettingsExecutionNotificationRecipient:
    def stock_withdrawal_recipient(self) -> str:
        return settings.smtp_from


class SmtpExecutionEmailSender:
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        await send_email(to, subject, body, html)
