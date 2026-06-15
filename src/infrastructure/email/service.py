import os

import aiosmtplib
from email.message import EmailMessage

from src.config import settings


async def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    if os.getenv("TESTING") == "1":
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=False,
    )
