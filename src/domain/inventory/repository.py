from typing import Protocol

from src.domain.inventory.entity import GoodsReceipt, PurchaseRequest, Reservation


class InventoryRepository(Protocol):
    def add_reservation(self, reservation: Reservation) -> Reservation:
        ...

    def list_active_reservations_for_service_order(
        self,
        service_order_id: int,
    ) -> list[Reservation]:
        ...

    def list_reservations(self) -> list[Reservation]:
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

    def add_receipt(self, receipt: GoodsReceipt) -> GoodsReceipt:
        ...
