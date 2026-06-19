from src.application.ports.service_order import (
    ServiceOrderContactLookup,
    ServiceOrderEmailSender,
    ServiceOrderPdfGenerator,
)
from src.domain.exceptions import NotFoundError
from src.domain.service_order.repository import ServiceOrderRepository


class ServiceOrderEmailService:
    def __init__(
        self,
        service_orders: ServiceOrderRepository,
        contacts: ServiceOrderContactLookup,
        pdfs: ServiceOrderPdfGenerator,
        emails: ServiceOrderEmailSender,
    ):
        self.service_orders = service_orders
        self.contacts = contacts
        self.pdfs = pdfs
        self.emails = emails

    async def send_os_email(self, service_order_id: int) -> None:
        service_order = self.service_orders.get_by_id(service_order_id)
        if not service_order:
            raise NotFoundError("OS não encontrada")
        if service_order.id is None:
            raise NotFoundError("OS não encontrada")
        customer = self.contacts.get_customer(service_order.customer_id)
        vehicle = self.contacts.get_vehicle(service_order.vehicle_id)

        self.pdfs.generate_service_order_pdf(
            service_order.id,
            customer.name if customer else "",
            vehicle.plate if vehicle else "",
            service_order.status.value,
            service_order.mechanic_name,
            service_order.total_price,
        )
        await self.emails.send_email(
            customer.email,
            f"Ordem de Serviço #{service_order.id}",
            f"Sua OS #{service_order.id} está com status: {service_order.status.value}",
        )
