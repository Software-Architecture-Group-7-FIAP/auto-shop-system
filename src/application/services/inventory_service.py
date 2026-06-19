from src.application.ports.inventory import (
    InventoryProductGateway,
    InventoryServiceOrderLookup,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.exceptions import NotFoundError
from src.domain.inventory.entity import GoodsReceipt, PurchaseRequest, Reservation
from src.domain.inventory.repository import InventoryRepository


class InventoryService:
    def __init__(
        self,
        inventory: InventoryRepository,
        products: InventoryProductGateway,
        service_orders: InventoryServiceOrderLookup,
        uow: UnitOfWork,
    ):
        self.inventory = inventory
        self.products = products
        self.service_orders = service_orders
        self.uow = uow

    def create_reservation(
        self,
        service_order_id: int,
        product_id: int,
        quantity: int,
    ) -> Reservation:
        reservation = self.inventory.add_reservation(
            Reservation.create(service_order_id, product_id, quantity)
        )
        self.uow.commit()
        return reservation

    def create_reservations_for_os(self, service_order_id: int) -> list[Reservation]:
        product_lines = self.service_orders.get_product_lines(service_order_id)
        if product_lines is None:
            raise NotFoundError("OS não encontrada")

        reservations = []
        for line in product_lines:
            product = self.products.get_product(line.product_id)
            if not product:
                continue
            available = self._available_stock(product.id, product.stock_quantity)
            if available < line.quantity and not self.check_pending_receipt(product.id):
                self._create_purchase_request(
                    product.id,
                    line.quantity - available,
                    service_order_id,
                )
            reservation = self.inventory.add_reservation(
                Reservation.create(service_order_id, line.product_id, line.quantity)
            )
            reservations.append(reservation)
        self.uow.commit()
        return reservations

    def _available_stock(self, product_id: int, stock_quantity: int) -> int:
        return stock_quantity - self.inventory.active_quantity_for_product(product_id)

    def check_pending_receipt(self, product_id: int) -> bool:
        return self.inventory.has_pending_receipt(product_id)

    def create_purchase_request(
        self,
        product_id: int,
        quantity: int,
        service_order_id: int | None = None,
    ) -> PurchaseRequest:
        purchase_request = self._create_purchase_request(
            product_id,
            quantity,
            service_order_id,
        )
        self.uow.commit()
        return purchase_request

    def _create_purchase_request(
        self,
        product_id: int,
        quantity: int,
        service_order_id: int | None,
    ) -> PurchaseRequest:
        product = self.products.get_product(product_id)
        if not product:
            raise NotFoundError("Produto não encontrado")
        return self.inventory.add_purchase_request(
            PurchaseRequest.create(
                product_id=product_id,
                quantity=quantity,
                supplier_id=product.supplier_id,
                service_order_id=service_order_id,
            )
        )

    def list_purchase_requests(self) -> list[PurchaseRequest]:
        return self.inventory.list_purchase_requests()

    def list_reservations(self) -> list[Reservation]:
        return self.inventory.list_reservations()

    def register_receipt(self, purchase_request_id: int, quantity: int) -> GoodsReceipt:
        purchase_request = self.inventory.get_purchase_request(purchase_request_id)
        if not purchase_request:
            raise NotFoundError("Solicitação de compra não encontrada")

        receipt = self.inventory.add_receipt(
            GoodsReceipt.create(purchase_request_id, quantity)
        )
        self.products.add_stock(purchase_request.product_id, quantity)
        purchase_request.mark_received()
        self.inventory.save_purchase_request(purchase_request)
        self.uow.commit()
        return receipt

    def get_pending_receipts(self, product_id: int) -> list[PurchaseRequest]:
        return self.inventory.get_pending_receipts(product_id)
