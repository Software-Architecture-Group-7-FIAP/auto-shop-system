from dataclasses import dataclass
from typing import Protocol

from src.application.ports.email import EmailAttachment
from src.domain.inventory.entity import Reservation


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


@dataclass(frozen=True)
class ServiceOrderCatalogService:
    id: int
    base_price: float


@dataclass(frozen=True)
class ServiceOrderProduct:
    id: int
    unit_price: float


@dataclass(frozen=True)
class RequestedService:
    service_id: int
    quantity: int


@dataclass(frozen=True)
class RequestedPart:
    product_id: int
    quantity: int


class ServiceOrderOpeningLookup(Protocol):
    def customer_exists(self, customer_id: int) -> bool:
        ...

    def vehicle_belongs_to_customer(self, vehicle_id: int, customer_id: int) -> bool:
        ...

    def get_service(self, service_id: int) -> ServiceOrderCatalogService | None:
        ...

    def get_product(self, product_id: int) -> ServiceOrderProduct | None:
        ...


class ServiceOrderStockReserver(Protocol):
    def create_reservations_for_os(self, service_order_id: int) -> list[Reservation]:
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
