from src.application.ports.email import EmailAttachment
from src.application.ports.service_order import (
    ServiceOrderContactLookup,
    ServiceOrderEmailSender,
    ServiceOrderPdfGenerator,
)
from src.application.ports.service_order_tracking import ServiceOrderTrackingTokenService
from src.application.ports.unit_of_work import UnitOfWork
from src.application.services.service_order_tracking import build_service_order_tracking_url
from src.domain.exceptions import NotFoundError
from src.domain.service_order.repository import ServiceOrderRepository


class ServiceOrderEmailService:
    def __init__(
        self,
        service_orders: ServiceOrderRepository,
        contacts: ServiceOrderContactLookup,
        pdfs: ServiceOrderPdfGenerator,
        emails: ServiceOrderEmailSender,
        tracking_tokens: ServiceOrderTrackingTokenService,
        frontend_public_url: str,
        uow: UnitOfWork,
    ):
        self.service_orders = service_orders
        self.contacts = contacts
        self.pdfs = pdfs
        self.emails = emails
        self.tracking_tokens = tracking_tokens
        self.frontend_public_url = frontend_public_url
        self.uow = uow

    async def send_os_email(self, service_order_id: int) -> None:
        service_order = self.service_orders.get_by_id(service_order_id)
        if not service_order:
            raise NotFoundError("OS não encontrada")
        if service_order.id is None:
            raise NotFoundError("OS não encontrada")
        customer = self.contacts.get_customer(service_order.customer_id)
        vehicle = self.contacts.get_vehicle(service_order.vehicle_id)
        if not customer or not vehicle:
            raise NotFoundError("Dados da OS não encontrados")
        token = self.tracking_tokens.create_token()
        tracking_url = build_service_order_tracking_url(self.frontend_public_url, token)

        pdf = self.pdfs.generate_service_order_pdf(
            service_order.id,
            customer.name,
            vehicle.plate,
            service_order.status.value,
            service_order.mechanic_name,
            service_order.total_price,
            tracking_url,
        )
        body = (
            f"Sua OS #{service_order.id} está com status: {service_order.status.value}.\n\n"
            f"Acompanhe sua OS:\n{tracking_url}\n\n"
            "Use o link acima para consultar o progresso."
        )
        await self.emails.send_email(
            customer.email,
            f"Ordem de Serviço #{service_order.id}",
            body,
            attachments=(
                EmailAttachment(
                    filename=f"ordem-servico-{service_order.id}.pdf",
                    content=pdf,
                    mime_type="application/pdf",
                ),
            ),
        )
        self.service_orders.set_tracking_token_fingerprint(
            service_order.id,
            self.tracking_tokens.fingerprint(token),
            # The link remains usable throughout the repair. Delivery starts
            # the seven-day retention window in the persistence adapter.
            None,
        )
        self.uow.commit()
