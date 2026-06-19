from dataclasses import dataclass
from datetime import datetime

from src.domain.enums import PurchaseRequestStatus, ReservationStatus
from src.domain.exceptions import ValidationError


@dataclass
class Reservation:
    id: int | None
    service_order_id: int
    product_id: int
    quantity: int
    status: ReservationStatus = ReservationStatus.ACTIVE
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        service_order_id: int,
        product_id: int,
        quantity: int,
    ) -> "Reservation":
        return cls(
            id=None,
            service_order_id=service_order_id,
            product_id=product_id,
            quantity=positive_quantity(quantity),
        )


@dataclass
class PurchaseRequest:
    id: int | None
    product_id: int
    quantity: int
    supplier_id: int | None = None
    service_order_id: int | None = None
    status: PurchaseRequestStatus = PurchaseRequestStatus.PENDING
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        product_id: int,
        quantity: int,
        supplier_id: int | None,
        service_order_id: int | None,
    ) -> "PurchaseRequest":
        return cls(
            id=None,
            product_id=product_id,
            quantity=positive_quantity(quantity),
            supplier_id=supplier_id,
            service_order_id=service_order_id,
        )

    def mark_received(self) -> None:
        self.status = PurchaseRequestStatus.RECEIVED


@dataclass
class GoodsReceipt:
    id: int | None
    purchase_request_id: int
    quantity: int
    received_at: datetime | None = None

    @classmethod
    def create(cls, purchase_request_id: int, quantity: int) -> "GoodsReceipt":
        return cls(
            id=None,
            purchase_request_id=purchase_request_id,
            quantity=positive_quantity(quantity),
        )


def positive_quantity(quantity: int) -> int:
    if quantity <= 0:
        raise ValidationError("Quantidade deve ser maior que zero")
    return quantity
