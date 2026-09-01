from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from src.application.ports.inventory import (
    InventoryProduct,
    InventoryServiceOrderProductLine,
    InventoryServiceOrderSnapshot,
)
from src.application.services.inventory_service import InventoryService
from src.domain.enums import PurchaseRequestStatus, ReservationStatus, ServiceOrderStatus
from src.domain.exceptions import NotFoundError
from src.domain.inventory.entity import GoodsReceipt, PurchaseRequest, Reservation


class InMemoryInventoryRepository:
    def __init__(self):
        self.reservations: dict[int, Reservation] = {}
        self.purchase_requests: dict[int, PurchaseRequest] = {}
        self.receipts: dict[int, GoodsReceipt] = {}
        self.next_reservation_id = 1
        self.next_purchase_request_id = 1
        self.next_receipt_id = 1

    def add_reservation(self, reservation: Reservation) -> Reservation:
        created = replace(reservation, id=self.next_reservation_id)
        self.reservations[created.id] = created
        self.next_reservation_id += 1
        return created

    def list_reservations(self) -> list[Reservation]:
        return list(self.reservations.values())

    def get_active_reservation(
        self,
        service_order_id: int,
        product_id: int,
        *,
        for_update: bool = False,
    ) -> Reservation | None:
        return next(
            (
                reservation
                for reservation in self.reservations.values()
                if reservation.service_order_id == service_order_id
                and reservation.product_id == product_id
                and reservation.status == ReservationStatus.ACTIVE
            ),
            None,
        )

    def save_reservation(self, reservation: Reservation) -> Reservation:
        assert reservation.id is not None
        self.reservations[reservation.id] = reservation
        return reservation

    def release_active_for_service_order(self, service_order_id: int) -> None:
        for reservation in self.reservations.values():
            if (
                reservation.service_order_id == service_order_id
                and reservation.status == ReservationStatus.ACTIVE
            ):
                reservation.release()

    def active_quantity_for_product(self, product_id: int) -> int:
        return sum(
            reservation.quantity
            for reservation in self.reservations.values()
            if reservation.product_id == product_id
            and reservation.status == ReservationStatus.ACTIVE
        )

    def add_purchase_request(
        self,
        purchase_request: PurchaseRequest,
    ) -> PurchaseRequest:
        created = replace(purchase_request, id=self.next_purchase_request_id)
        self.purchase_requests[created.id] = created
        self.next_purchase_request_id += 1
        return created

    def get_pending_purchase_request(
        self,
        service_order_id: int,
        product_id: int,
        *,
        for_update: bool = False,
    ) -> PurchaseRequest | None:
        return next(
            (
                request
                for request in self.purchase_requests.values()
                if request.service_order_id == service_order_id
                and request.product_id == product_id
                and request.status
                in (PurchaseRequestStatus.PENDING, PurchaseRequestStatus.ORDERED)
            ),
            None,
        )

    def save_purchase_request(self, purchase_request: PurchaseRequest) -> PurchaseRequest:
        assert purchase_request.id is not None
        self.purchase_requests[purchase_request.id] = purchase_request
        return purchase_request

    def get_purchase_request(self, purchase_request_id: int) -> PurchaseRequest | None:
        return self.purchase_requests.get(purchase_request_id)

    def list_purchase_requests(self) -> list[PurchaseRequest]:
        return list(self.purchase_requests.values())

    def has_pending_receipt(self, product_id: int) -> bool:
        return any(
            purchase_request.product_id == product_id
            and purchase_request.status
            in (PurchaseRequestStatus.PENDING, PurchaseRequestStatus.ORDERED)
            for purchase_request in self.purchase_requests.values()
        )

    def get_pending_receipts(self, product_id: int) -> list[PurchaseRequest]:
        return [
            purchase_request
            for purchase_request in self.purchase_requests.values()
            if purchase_request.product_id == product_id
            and purchase_request.status
            in (PurchaseRequestStatus.PENDING, PurchaseRequestStatus.ORDERED)
        ]

    def add_receipt(self, receipt: GoodsReceipt) -> GoodsReceipt:
        created = replace(receipt, id=self.next_receipt_id)
        self.receipts[created.id] = created
        self.next_receipt_id += 1
        return created


class FakeProductGateway:
    def __init__(self, products: dict[int, InventoryProduct]):
        self.products = products

    def get_product(self, product_id: int) -> InventoryProduct | None:
        return self.products.get(product_id)

    def get_product_for_update(self, product_id: int) -> InventoryProduct | None:
        return self.get_product(product_id)

    def add_stock(self, product_id: int, quantity: int) -> None:
        product = self.products.get(product_id)
        if product:
            self.products[product_id] = replace(
                product,
                stock_quantity=product.stock_quantity + quantity,
            )


class FakeServiceOrderLookup:
    def __init__(
        self,
        product_lines: dict[int, list[InventoryServiceOrderProductLine]],
    ):
        self.snapshots = {
            service_order_id: InventoryServiceOrderSnapshot(
                id=service_order_id,
                status=ServiceOrderStatus.AGUARDANDO_INICIO,
                product_lines=tuple(lines),
                created_at=datetime(2026, 1, 1) + timedelta(days=service_order_id),
            )
            for service_order_id, lines in product_lines.items()
        }

    def get_product_lines(
        self,
        service_order_id: int,
    ) -> list[InventoryServiceOrderProductLine] | None:
        snapshot = self.get_reservation_snapshot(service_order_id)
        return list(snapshot.product_lines) if snapshot else None

    def get_reservation_snapshot(
        self,
        service_order_id: int,
    ) -> InventoryServiceOrderSnapshot | None:
        return self.snapshots.get(service_order_id)

    def list_reservation_queue(
        self,
        product_id: int,
    ) -> list[InventoryServiceOrderSnapshot]:
        return sorted(
            [
                snapshot
                for snapshot in self.snapshots.values()
                if snapshot.status
                in {
                    ServiceOrderStatus.AGUARDANDO_INICIO,
                    ServiceOrderStatus.AGUARDANDO_COMPRA,
                }
                and any(line.product_id == product_id for line in snapshot.product_lines)
            ],
            key=lambda snapshot: (snapshot.created_at or datetime.max, snapshot.id),
        )

    def set_reservation_status(
        self,
        service_order_id: int,
        status: ServiceOrderStatus,
    ) -> None:
        snapshot = self.snapshots[service_order_id]
        self.snapshots[service_order_id] = replace(snapshot, status=status)


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def make_service(
    inventory: InMemoryInventoryRepository | None = None,
    products: FakeProductGateway | None = None,
    service_orders: FakeServiceOrderLookup | None = None,
    uow: FakeUnitOfWork | None = None,
) -> InventoryService:
    return InventoryService(
        inventory=inventory or InMemoryInventoryRepository(),
        products=products
        or FakeProductGateway(
            {1: InventoryProduct(id=1, stock_quantity=10, supplier_id=2)}
        ),
        service_orders=service_orders
        or FakeServiceOrderLookup(
            {1: [InventoryServiceOrderProductLine(product_id=1, quantity=3)]}
        ),
        uow=uow or FakeUnitOfWork(),
    )


def test_inventory_service_creates_reservation_without_sqlalchemy():
    inventory = InMemoryInventoryRepository()
    uow = FakeUnitOfWork()
    service = make_service(inventory=inventory, uow=uow)

    reservation = service.create_reservation(1, 1, 3)

    assert reservation.id == 1
    assert reservation.status == ReservationStatus.ACTIVE
    assert inventory.list_reservations() == [reservation]
    assert uow.commits == 1


def test_inventory_service_creates_reservations_for_service_order():
    inventory = InMemoryInventoryRepository()
    uow = FakeUnitOfWork()
    service = make_service(inventory=inventory, uow=uow)

    reservations = service.create_reservations_for_os(1)

    assert len(reservations) == 1
    assert reservations[0].product_id == 1
    assert reservations[0].quantity == 3
    assert inventory.list_purchase_requests() == []
    assert uow.commits == 1


def test_inventory_service_creates_purchase_request_for_insufficient_stock():
    inventory = InMemoryInventoryRepository()
    service = make_service(
        inventory=inventory,
        products=FakeProductGateway(
            {1: InventoryProduct(id=1, stock_quantity=1, supplier_id=2)}
        ),
        service_orders=FakeServiceOrderLookup(
            {1: [InventoryServiceOrderProductLine(product_id=1, quantity=5)]}
        ),
    )

    service.create_reservations_for_os(1)

    purchase_requests = inventory.list_purchase_requests()
    assert len(purchase_requests) == 1
    assert purchase_requests[0].product_id == 1
    assert purchase_requests[0].quantity == 4
    assert purchase_requests[0].supplier_id == 2
    assert purchase_requests[0].service_order_id == 1


def test_inventory_service_does_not_duplicate_pending_receipt():
    inventory = InMemoryInventoryRepository()
    inventory.add_purchase_request(
        PurchaseRequest.create(
            product_id=1,
            quantity=4,
            supplier_id=2,
            service_order_id=1,
        )
    )
    service = make_service(
        inventory=inventory,
        products=FakeProductGateway(
            {1: InventoryProduct(id=1, stock_quantity=1, supplier_id=2)}
        ),
        service_orders=FakeServiceOrderLookup(
            {1: [InventoryServiceOrderProductLine(product_id=1, quantity=5)]}
        ),
    )

    service.create_reservations_for_os(1)

    assert len(inventory.list_purchase_requests()) == 1


def test_inventory_service_rejects_missing_service_order():
    service = make_service(service_orders=FakeServiceOrderLookup({}))

    with pytest.raises(NotFoundError, match="OS não encontrada"):
        service.create_reservations_for_os(1)


def test_inventory_service_creates_purchase_request():
    inventory = InMemoryInventoryRepository()
    service = make_service(inventory=inventory)

    purchase_request = service.create_purchase_request(1, 5, service_order_id=2)

    assert purchase_request.id == 1
    assert purchase_request.product_id == 1
    assert purchase_request.quantity == 5
    assert purchase_request.supplier_id == 2


def test_inventory_service_rejects_missing_product():
    service = make_service(products=FakeProductGateway({}))

    with pytest.raises(NotFoundError, match="Produto não encontrado"):
        service.create_purchase_request(1, 5)


def test_inventory_service_registers_receipt_and_updates_stock():
    inventory = InMemoryInventoryRepository()
    products = FakeProductGateway(
        {1: InventoryProduct(id=1, stock_quantity=10, supplier_id=2)}
    )
    purchase_request = inventory.add_purchase_request(
        PurchaseRequest.create(
            product_id=1,
            quantity=4,
            supplier_id=2,
            service_order_id=None,
        )
    )
    uow = FakeUnitOfWork()
    service = make_service(inventory=inventory, products=products, uow=uow)

    receipt = service.register_receipt(purchase_request.id, 4)

    assert receipt.purchase_request_id == purchase_request.id
    assert receipt.quantity == 4
    assert inventory.get_purchase_request(purchase_request.id).status == PurchaseRequestStatus.RECEIVED
    assert products.get_product(1).stock_quantity == 14
    assert uow.commits == 1


def test_inventory_service_lists_pending_receipts():
    inventory = InMemoryInventoryRepository()
    pending = inventory.add_purchase_request(
        PurchaseRequest.create(
            product_id=1,
            quantity=4,
            supplier_id=2,
            service_order_id=None,
        )
    )
    received = inventory.add_purchase_request(
        PurchaseRequest.create(
            product_id=1,
            quantity=2,
            supplier_id=2,
            service_order_id=None,
        )
    )
    received.mark_received()
    inventory.save_purchase_request(received)
    service = make_service(inventory=inventory)

    assert service.get_pending_receipts(1) == [pending]
