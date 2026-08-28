from dataclasses import dataclass
from typing import Protocol

from src.application.ports.email import EmailAttachment
from src.domain.service_order.entity import ServiceOrderStatusTransition


@dataclass(frozen=True)
class ServiceOrderCustomer:
    name: str
    email: str
    documents: tuple[str, ...]


@dataclass(frozen=True)
class ServiceOrderVehicle:
    plate: str


class ServiceOrderContactLookup(Protocol):
    def get_customer(self, customer_id: int) -> ServiceOrderCustomer | None:
        ...

    def get_vehicle(self, vehicle_id: int) -> ServiceOrderVehicle | None:
        ...


class ServiceOrderStatusHistoryRepository(Protocol):
    """Append-only sink for workflow audit entries.

    The aggregate also keeps entries in memory for unit-of-work consumers; a
    persistence adapter can project them into a dedicated history table.
    """

    def append(self, service_order_id: int, transition: ServiceOrderStatusTransition) -> None:
        ...


class ServiceOrderPdfGenerator(Protocol):
    def generate_service_order_pdf(
        self,
        service_order_id: int,
        customer_name: str,
        vehicle_plate: str,
        status: str,
        mechanic_name: str | None,
        total_price: float,
        tracking_url: str,
    ) -> bytes:
        ...


class ServiceOrderEmailSender(Protocol):
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
        attachments: tuple[EmailAttachment, ...] = (),
    ) -> None:
        ...
