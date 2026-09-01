from datetime import datetime

from src.application.ports.inventory import (
    InventoryProduct,
    InventoryProductGateway,
    InventoryServiceOrderLookup,
    InventoryServiceOrderProductLine,
    InventoryServiceOrderSnapshot,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.enums import PurchaseRequestStatus, ReservationStatus, ServiceOrderStatus
from src.domain.exceptions import NotFoundError, ValidationError
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
        snapshot = self._get_snapshot(service_order_id)
        self._ensure_snapshot_exists(snapshot)
        self._ensure_reservable(snapshot)
        if product_id not in self._required_by_product(snapshot.product_lines):
            raise ValidationError(
                f"Produto #{product_id} não está no escopo da OS #{service_order_id}"
            )
        product = self._get_product_for_update(product_id)
        if product is None:
            raise NotFoundError("Produto não encontrado")
        reservation = self._reserve_quantity(service_order_id, product, quantity)
        self._refresh_queue_statuses(service_order_id)
        self.uow.commit()
        return reservation

    def create_reservations_for_os(self, service_order_id: int) -> list[Reservation]:
        reservations = self.reconcile_for_service_order(service_order_id)
        self.uow.commit()
        return reservations

    def reconcile_reservations_for_os(self, service_order_id: int) -> list[Reservation]:
        reservations = self.reconcile_for_service_order(service_order_id)
        self.uow.commit()
        return reservations

    def reconcile_for_service_order(self, service_order_id: int) -> list[Reservation]:
        snapshot = self._get_snapshot(service_order_id)
        self._ensure_snapshot_exists(snapshot)
        if snapshot.status not in {
            ServiceOrderStatus.AGUARDANDO_INICIO,
            ServiceOrderStatus.AGUARDANDO_COMPRA,
        }:
            self.inventory.release_active_for_service_order(service_order_id)
            self.inventory.cancel_pending_purchase_requests_for_service_order(
                service_order_id
            )
            return []

        required = self._required_by_product(snapshot.product_lines)
        self._release_removed_product_reservations(service_order_id, required)
        for product_id in sorted(required):
            self._reconcile_product_queue(product_id, service_order_id)

        self._refresh_queue_statuses(service_order_id)
        return sorted(
            (
                reservation
                for reservation in self.inventory.list_reservations()
                if reservation.service_order_id == service_order_id
                and reservation.status == ReservationStatus.ACTIVE
            ),
            key=lambda reservation: reservation.product_id,
        )

    def _reconcile_product_queue(
        self,
        product_id: int,
        requested_service_order_id: int,
    ) -> None:
        product = self._get_product_for_update(product_id)
        if product is None:
            return

        queue = self.service_orders.list_reservation_queue(product_id)
        requested_snapshot = self._get_snapshot(requested_service_order_id)
        if requested_snapshot is not None and requested_snapshot.id not in {
            item.id for item in queue
        }:
            queue = [*queue, requested_snapshot]
            queue.sort(key=self._reservation_queue_key)

        queue_ids = {item.id for item in queue}
        reserved_outside_queue = sum(
            reservation.quantity
            for reservation in self.inventory.list_reservations()
            if reservation.product_id == product_id
            and reservation.status == ReservationStatus.ACTIVE
            and reservation.service_order_id not in queue_ids
        )
        remaining = max(product.stock_quantity - reserved_outside_queue, 0)

        for item in queue:
            required = self._required_by_product(item.product_lines).get(product_id, 0)
            current = self.inventory.get_active_reservation(
                item.id,
                product_id,
                for_update=True,
            )
            desired = min(required, remaining)
            if current is not None:
                if desired == 0:
                    current.release()
                    self.inventory.save_reservation(current)
                elif current.quantity != desired:
                    current.reconcile_quantity(desired)
                    self.inventory.save_reservation(current)
            elif desired > 0:
                self.inventory.add_reservation(
                    Reservation.create(item.id, product_id, desired)
                )
            remaining -= desired
            self._reconcile_backorder(
                item.id,
                product,
                required - desired,
            )

    def _refresh_queue_statuses(self, requested_service_order_id: int) -> None:
        requested = self._get_snapshot(requested_service_order_id)
        if requested is None:
            return
        queue_by_product: dict[int, list[InventoryServiceOrderSnapshot]] = {}
        for line in requested.product_lines:
            queue_by_product[line.product_id] = self.service_orders.list_reservation_queue(
                line.product_id
            )

        candidates = {
            item.id: item
            for queue in queue_by_product.values()
            for item in queue
        }
        candidates[requested.id] = requested
        active_quantity = {
            (reservation.service_order_id, reservation.product_id): reservation.quantity
            for reservation in self.inventory.list_reservations()
            if reservation.status == ReservationStatus.ACTIVE
        }
        for item in candidates.values():
            required = self._required_by_product(item.product_lines)
            has_shortage = any(
                active_quantity.get((item.id, product_id), 0) < quantity
                for product_id, quantity in required.items()
            )
            target = (
                ServiceOrderStatus.AGUARDANDO_COMPRA
                if has_shortage
                else ServiceOrderStatus.AGUARDANDO_INICIO
            )
            if item.status != target:
                self.service_orders.set_reservation_status(item.id, target)

    def release_for_service_order(self, service_order_id: int) -> None:
        self.inventory.release_active_for_service_order(service_order_id)
        self.inventory.cancel_pending_purchase_requests_for_service_order(
            service_order_id
        )

    def release_reservations_for_os(self, service_order_id: int) -> None:
        snapshot = self._get_snapshot(service_order_id)
        self._ensure_snapshot_exists(snapshot)
        self.release_for_service_order(service_order_id)
        self.uow.commit()

    def _reserve_quantity(
        self,
        service_order_id: int,
        product: InventoryProduct,
        quantity: int,
    ) -> Reservation:
        if quantity <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")
        current = self.inventory.get_active_reservation(
            service_order_id,
            product.id,
            for_update=True,
        )
        current_quantity = current.quantity if current else 0
        other_active = self.inventory.active_quantity_for_product(product.id) - current_quantity
        available = max(product.stock_quantity - max(other_active, 0), 0)
        desired = min(quantity, available)
        self._reconcile_backorder(service_order_id, product, quantity - desired)
        if desired <= 0:
            raise ValidationError("Estoque físico insuficiente para reserva")
        if current is None:
            return self.inventory.add_reservation(
                Reservation.create(service_order_id, product.id, desired)
            )
        if current.quantity != desired:
            current.reconcile_quantity(desired)
            return self.inventory.save_reservation(current)
        return current

    def _reconcile_product(
        self,
        service_order_id: int,
        product: InventoryProduct,
        required_quantity: int,
    ) -> None:
        current = self.inventory.get_active_reservation(
            service_order_id,
            product.id,
            for_update=True,
        )
        current_quantity = current.quantity if current else 0
        other_active = self.inventory.active_quantity_for_product(product.id) - current_quantity
        available = max(product.stock_quantity - max(other_active, 0), 0)
        desired = min(required_quantity, available)

        if current is not None:
            if desired == 0:
                current.release()
                self.inventory.save_reservation(current)
            elif current.quantity != desired:
                current.reconcile_quantity(desired)
                self.inventory.save_reservation(current)
        elif desired > 0:
            self.inventory.add_reservation(
                Reservation.create(service_order_id, product.id, desired)
            )

        self._reconcile_backorder(
            service_order_id,
            product,
            required_quantity - desired,
        )

    def _reconcile_backorder(
        self,
        service_order_id: int,
        product: InventoryProduct,
        missing_quantity: int,
    ) -> None:
        existing = self.inventory.get_pending_purchase_request(
            service_order_id,
            product.id,
            for_update=True,
        )
        if missing_quantity <= 0:
            if existing is not None:
                existing.cancel()
                self.inventory.save_purchase_request(existing)
            return
        if existing is not None:
            existing.reconcile_quantity(missing_quantity)
            self.inventory.save_purchase_request(existing)
            return
        self.inventory.add_purchase_request(
            PurchaseRequest.create(
                product_id=product.id,
                quantity=missing_quantity,
                supplier_id=product.supplier_id,
                service_order_id=service_order_id,
            )
        )

    def _release_removed_product_reservations(
        self,
        service_order_id: int,
        required: dict[int, int],
    ) -> None:
        for reservation in self.inventory.list_reservations():
            if (
                reservation.service_order_id == service_order_id
                and reservation.status == ReservationStatus.ACTIVE
                and reservation.product_id not in required
            ):
                reservation.release()
                self.inventory.save_reservation(reservation)

    def _get_snapshot(self, service_order_id: int) -> InventoryServiceOrderSnapshot | None:
        return self.service_orders.get_reservation_snapshot(service_order_id)

    @staticmethod
    def _ensure_snapshot_exists(
        snapshot: InventoryServiceOrderSnapshot | None,
    ) -> None:
        if snapshot is None:
            raise NotFoundError("OS não encontrada")

    @staticmethod
    def _ensure_reservable(snapshot: InventoryServiceOrderSnapshot) -> None:
        if snapshot.status != ServiceOrderStatus.AGUARDANDO_INICIO:
            raise ValidationError(
                "Reserva só é permitida quando a OS aguarda início"
            )

    def _get_product_for_update(self, product_id: int) -> InventoryProduct | None:
        return self.products.get_product_for_update(product_id)

    @staticmethod
    def _reservation_queue_key(
        snapshot: InventoryServiceOrderSnapshot,
    ) -> tuple[object, int]:
        """Keep in-memory and SQL-backed allocation order identical."""
        return (snapshot.created_at or datetime.max, snapshot.id)

    @staticmethod
    def _required_by_product(
        product_lines: tuple[InventoryServiceOrderProductLine, ...]
        | list[InventoryServiceOrderProductLine],
    ) -> dict[int, int]:
        required: dict[int, int] = {}
        for line in product_lines:
            required[line.product_id] = required.get(line.product_id, 0) + line.quantity
        return required

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
        if service_order_id is not None:
            existing = self.inventory.get_pending_purchase_request(
                service_order_id,
                product_id,
            )
            if existing is not None:
                existing.reconcile_quantity(existing.quantity + quantity)
                return self.inventory.save_purchase_request(existing)
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
        if purchase_request.service_order_id is not None:
            self.reconcile_for_service_order(purchase_request.service_order_id)
        self.uow.commit()
        return receipt

    def get_pending_receipts(self, product_id: int) -> list[PurchaseRequest]:
        return self.inventory.get_pending_receipts(product_id)

    def check_pending_receipt(self, product_id: int) -> bool:
        return self.inventory.has_pending_receipt(product_id)
