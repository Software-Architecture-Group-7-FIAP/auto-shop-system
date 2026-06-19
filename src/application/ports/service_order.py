from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ServiceOrderCustomer:
    name: str
    email: str
    document: str


@dataclass(frozen=True)
class ServiceOrderVehicle:
    plate: str


class ServiceOrderContactLookup(Protocol):
    def get_customer(self, customer_id: int) -> ServiceOrderCustomer | None:
        ...

    def get_vehicle(self, vehicle_id: int) -> ServiceOrderVehicle | None:
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
    ) -> bytes:
        ...


class ServiceOrderEmailSender(Protocol):
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        ...
