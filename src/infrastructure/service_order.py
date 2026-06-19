from src.infrastructure.email.service import send_email
from src.infrastructure.pdf.generator import generate_service_order_pdf


class ReportLabServiceOrderPdfGenerator:
    def generate_service_order_pdf(
        self,
        service_order_id: int,
        customer_name: str,
        vehicle_plate: str,
        status: str,
        mechanic_name: str | None,
        total_price: float,
    ) -> bytes:
        return generate_service_order_pdf(
            service_order_id,
            customer_name,
            vehicle_plate,
            status,
            mechanic_name,
            total_price,
        )


class SmtpServiceOrderEmailSender:
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        await send_email(to, subject, body, html)
