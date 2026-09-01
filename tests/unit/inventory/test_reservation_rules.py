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
from src.domain.inventory.entity import PurchaseRequest, Reservation


class InMemoryInventoryRepository:
    def __init__(self) -> None:
        self.reservations: dict[int, Reservation] = {}
        self.purchase_requests: dict[int, PurchaseRequest] = {}
        self.receipts: dict[int, object] = {}
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

    def active_quantity_for_product(self, product_id: int) -> int:
        return sum(
            item.quantity
            for item in self.reservations.values()
            if item.product_id == product_id and item.status == ReservationStatus.ACTIVE
        )

    def get_active_reservation(self, service_order_id: int, product_id: int, *, for_update: bool = False) -> Reservation | None:
        return next(
            (
                item
                for item in self.reservations.values()
                if item.service_order_id == service_order_id
                and item.product_id == product_id
                and item.status == ReservationStatus.ACTIVE
            ),
            None,
        )

    def save_reservation(self, reservation: Reservation) -> Reservation:
        assert reservation.id is not None
        self.reservations[reservation.id] = reservation
        return reservation

    def release_active_for_service_order(self, service_order_id: int) -> None:
        for item in self.reservations.values():
            if item.service_order_id == service_order_id and item.status == ReservationStatus.ACTIVE:
                item.status = ReservationStatus.RELEASED

    def get_purchase_request(self, purchase_request_id: int) -> PurchaseRequest | None:
        return self.purchase_requests.get(purchase_request_id)

    def add_purchase_request(self, request: PurchaseRequest) -> PurchaseRequest:
        created = replace(request, id=self.next_purchase_request_id)
        self.purchase_requests[created.id] = created
        self.next_purchase_request_id += 1
        return created

    def get_pending_purchase_request(self, service_order_id: int, product_id: int, *, for_update: bool = False) -> PurchaseRequest | None:
        return next(
            (
                item
                for item in self.purchase_requests.values()
                if item.service_order_id == service_order_id
                and item.product_id == product_id
                and item.status in (PurchaseRequestStatus.PENDING, PurchaseRequestStatus.ORDERED)
            ),
            None,
        )

    def save_purchase_request(self, request: PurchaseRequest) -> PurchaseRequest:
        assert request.id is not None
        self.purchase_requests[request.id] = request
        return request

    def cancel_pending_purchase_requests_for_service_order(self, service_order_id: int) -> None:
        for item in self.purchase_requests.values():
            if item.service_order_id == service_order_id and item.status in (
                PurchaseRequestStatus.PENDING,
                PurchaseRequestStatus.ORDERED,
            ):
                item.cancel()

    def add_receipt(self, receipt):
        created = replace(receipt, id=self.next_receipt_id)
        self.receipts[created.id] = created
        self.next_receipt_id += 1
        return created


class FakeProductGateway:
    def __init__(self, products: dict[int, InventoryProduct]) -> None:
        self.products = products

    def get_product(self, product_id: int) -> InventoryProduct | None:
        return self.products.get(product_id)

    def get_product_for_update(self, product_id: int) -> InventoryProduct | None:
        return self.get_product(product_id)

    def add_stock(self, product_id: int, quantity: int) -> None:
        product = self.products[product_id]
        self.products[product_id] = replace(product, stock_quantity=product.stock_quantity + quantity)


class FakeServiceOrderLookup:
    def __init__(
        self,
        snapshot: InventoryServiceOrderSnapshot,
        additional_snapshots: list[InventoryServiceOrderSnapshot] | None = None,
    ) -> None:
        snapshots = [snapshot, *(additional_snapshots or [])]
        self.snapshots = {item.id: item for item in snapshots}

    @property
    def snapshot(self) -> InventoryServiceOrderSnapshot:
        return self.snapshots[1]

    @snapshot.setter
    def snapshot(self, value: InventoryServiceOrderSnapshot) -> None:
        self.snapshots[value.id] = value

    def get_reservation_snapshot(self, service_order_id: int) -> InventoryServiceOrderSnapshot | None:
        return self.snapshots.get(service_order_id)

    def list_reservation_queue(self, product_id: int) -> list[InventoryServiceOrderSnapshot]:
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

    def set_reservation_status(self, service_order_id: int, status: ServiceOrderStatus) -> None:
        self.snapshots[service_order_id] = replace(
            self.snapshots[service_order_id], status=status
        )


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None


def make_service(
    *,
    stock: int = 10,
    quantity: int = 3,
    status: ServiceOrderStatus = ServiceOrderStatus.AGUARDANDO_INICIO,
) -> tuple[InventoryService, InMemoryInventoryRepository, FakeProductGateway, FakeUnitOfWork, FakeServiceOrderLookup]:
    inventory = InMemoryInventoryRepository()
    products = FakeProductGateway({1: InventoryProduct(id=1, stock_quantity=stock, supplier_id=2)})
    lookup = FakeServiceOrderLookup(
        InventoryServiceOrderSnapshot(
            id=1,
            status=status,
            product_lines=(InventoryServiceOrderProductLine(product_id=1, quantity=quantity),),
            created_at=datetime(2026, 1, 1),
        )
    )
    uow = FakeUnitOfWork()
    return InventoryService(inventory, products, lookup, uow), inventory, products, uow, lookup


def test_reconciliation_reserves_only_physical_stock_and_creates_backorder() -> None:
    service, inventory, _, _, lookup = make_service(stock=1, quantity=5)

    reservations = service.reconcile_reservations_for_os(1)

    assert [(item.product_id, item.quantity) for item in reservations] == [(1, 1)]
    request = inventory.get_pending_purchase_request(1, 1)
    assert request is not None
    assert request.quantity == 4
    assert lookup.snapshot.status == ServiceOrderStatus.AGUARDANDO_COMPRA


def test_reconciliation_is_idempotent_and_updates_existing_quantities() -> None:
    service, inventory, _, _, lookup = make_service(stock=10, quantity=3)

    service.reconcile_reservations_for_os(1)
    lookup.snapshot = replace(
        lookup.snapshot,
        product_lines=(InventoryServiceOrderProductLine(product_id=1, quantity=5),),
    )
    service.reconcile_reservations_for_os(1)
    service.reconcile_reservations_for_os(1)

    active = [item for item in inventory.list_reservations() if item.status == ReservationStatus.ACTIVE]
    assert len(active) == 1
    assert active[0].quantity == 5


@pytest.mark.parametrize(
    "status",
    [
        ServiceOrderStatus.RECEBIDA,
        ServiceOrderStatus.EM_DIAGNOSTICO,
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
    ],
)
def test_reconciliation_does_not_reserve_before_order_is_ready(status: ServiceOrderStatus) -> None:
    service, inventory, _, _, _ = make_service(status=status)

    assert service.reconcile_reservations_for_os(1) == []
    assert inventory.list_reservations() == []


def test_reconciliation_releases_reservations_and_pending_backorder() -> None:
    service, inventory, _, _, _ = make_service(stock=1, quantity=5)
    service.reconcile_reservations_for_os(1)

    service.release_reservations_for_os(1)

    assert all(item.status == ReservationStatus.RELEASED for item in inventory.list_reservations())
    request = inventory.get_pending_purchase_request(1, 1)
    assert request is None


def test_reconciliation_allocates_stock_in_approval_order_and_reprocesses_after_receipt() -> None:
    inventory = InMemoryInventoryRepository()
    products = FakeProductGateway({1: InventoryProduct(id=1, stock_quantity=3, supplier_id=2)})
    older = InventoryServiceOrderSnapshot(
        id=1,
        status=ServiceOrderStatus.AGUARDANDO_INICIO,
        product_lines=(InventoryServiceOrderProductLine(product_id=1, quantity=3),),
        created_at=datetime(2026, 1, 1),
    )
    newer = InventoryServiceOrderSnapshot(
        id=2,
        status=ServiceOrderStatus.AGUARDANDO_INICIO,
        product_lines=(InventoryServiceOrderProductLine(product_id=1, quantity=3),),
        created_at=datetime(2026, 1, 2),
    )
    lookup = FakeServiceOrderLookup(older, [newer])
    service = InventoryService(inventory, products, lookup, FakeUnitOfWork())

    service.reconcile_reservations_for_os(2)

    assert [(item.service_order_id, item.quantity) for item in inventory.list_reservations()] == [
        (1, 3)
    ]
    assert lookup.get_reservation_snapshot(1).status == ServiceOrderStatus.AGUARDANDO_INICIO
    assert lookup.get_reservation_snapshot(2).status == ServiceOrderStatus.AGUARDANDO_COMPRA
    request = inventory.get_pending_purchase_request(2, 1)
    assert request is not None
    assert request.quantity == 3

    service.register_receipt(request.id, 3)

    active = [
        item
        for item in inventory.list_reservations()
        if item.status == ReservationStatus.ACTIVE
    ]
    assert [(item.service_order_id, item.quantity) for item in active] == [(1, 3), (2, 3)]
    assert lookup.get_reservation_snapshot(2).status == ServiceOrderStatus.AGUARDANDO_INICIO
