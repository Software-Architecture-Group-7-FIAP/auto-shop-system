from typing import Protocol

from src.domain.inventory.entity import GoodsReceipt, PurchaseRequest, Reservation


class InventoryRepository(Protocol):
    def add_reservation(self, reservation: Reservation) -> Reservation:
        ...

    def list_reservations(self) -> list[Reservation]:
        ...

    def get_active_reservation(
        self,
        service_order_id: int,
        product_id: int,
        *,
        for_update: bool = False,
    ) -> Reservation | None:
        ...

    def save_reservation(self, reservation: Reservation) -> Reservation:
        ...

    def release_active_for_service_order(self, service_order_id: int) -> None:
        ...

    def active_quantity_for_product(self, product_id: int) -> int:
        ...

    def add_purchase_request(
        self,
        purchase_request: PurchaseRequest,
    ) -> PurchaseRequest:
        ...

    def get_purchase_request(self, purchase_request_id: int) -> PurchaseRequest | None:
        ...

    def save_purchase_request(
        self,
        purchase_request: PurchaseRequest,
    ) -> PurchaseRequest:
        ...

    def list_purchase_requests(self) -> list[PurchaseRequest]:
        ...

    def has_pending_receipt(self, product_id: int) -> bool:
        ...

    def get_pending_receipts(self, product_id: int) -> list[PurchaseRequest]:
        ...

    def get_pending_purchase_request(
        self,
        service_order_id: int,
        product_id: int,
        *,
        for_update: bool = False,
    ) -> PurchaseRequest | None:
        ...

    def cancel_pending_purchase_requests_for_service_order(
        self,
        service_order_id: int,
    ) -> None:
        ...

    def add_receipt(self, receipt: GoodsReceipt) -> GoodsReceipt:
        ...
