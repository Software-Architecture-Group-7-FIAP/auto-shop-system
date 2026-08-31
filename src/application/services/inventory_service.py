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

    def create_reservations_for_os(
        self,
        service_order_id: int,
        *,
        commit: bool = True,
    ) -> list[Reservation]:
        product_lines = self.service_orders.get_product_lines(service_order_id)
        if product_lines is None:
            raise NotFoundError("OS não encontrada")

        reservations = self.inventory.list_active_reservations_for_service_order(
            service_order_id
        )
        reserved_by_product: dict[int, int] = {}
        for reservation in reservations:
            reserved_by_product[reservation.product_id] = (
                reserved_by_product.get(reservation.product_id, 0) + reservation.quantity
            )

        required_by_product: dict[int, int] = {}
        for line in product_lines:
            required_by_product[line.product_id] = (
                required_by_product.get(line.product_id, 0) + line.quantity
            )

        for product_id, quantity in sorted(required_by_product.items()):
            quantity_to_reserve = quantity - reserved_by_product.get(product_id, 0)
            if quantity_to_reserve <= 0:
                continue

            product = self.products.get_product_for_update(product_id)
            if not product:
                continue
            available = self._available_stock(product.id, product.stock_quantity)
            if (
                available < quantity_to_reserve
                and not self.check_pending_receipt(product.id)
            ):
                self._create_purchase_request(
                    product.id,
                    quantity_to_reserve - available,
                    service_order_id,
                )
            reservation = self.inventory.add_reservation(
                Reservation.create(service_order_id, product.id, quantity_to_reserve)
            )
            reservations.append(reservation)
        if commit:
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
