import aiosmtplib
import os
from email.message import EmailMessage

from src.application.ports.email import EmailAttachment
from src.config import settings


async def send_email(
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
    attachments: tuple[EmailAttachment, ...] = (),
) -> None:
    if os.getenv("TESTING") == "1":
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    for attachment in attachments:
        maintype, subtype = attachment.mime_type.split("/", maxsplit=1)
        message.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password_value(),
        use_tls=settings.smtp_use_tls,
        start_tls=settings.smtp_starttls,
    )
