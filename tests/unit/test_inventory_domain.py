import pytest

from src.domain.enums import PurchaseRequestStatus, ReservationStatus
from src.domain.exceptions import ValidationError
from src.domain.inventory.entity import GoodsReceipt, PurchaseRequest, Reservation


def test_reservation_create_defaults_to_active_status():
    reservation = Reservation.create(
        service_order_id=1,
        product_id=2,
        quantity=3,
    )

    assert reservation.service_order_id == 1
    assert reservation.product_id == 2
    assert reservation.quantity == 3
    assert reservation.status == ReservationStatus.ACTIVE


def test_purchase_request_create_defaults_to_pending_status():
    purchase_request = PurchaseRequest.create(
        product_id=1,
        quantity=2,
        supplier_id=3,
        service_order_id=4,
    )

    assert purchase_request.product_id == 1
    assert purchase_request.quantity == 2
    assert purchase_request.supplier_id == 3
    assert purchase_request.service_order_id == 4
    assert purchase_request.status == PurchaseRequestStatus.PENDING


def test_purchase_request_mark_received_changes_status():
    purchase_request = PurchaseRequest.create(
        product_id=1,
        quantity=2,
        supplier_id=None,
        service_order_id=None,
    )

    purchase_request.mark_received()

    assert purchase_request.status == PurchaseRequestStatus.RECEIVED


def test_goods_receipt_rejects_non_positive_quantity():
    with pytest.raises(ValidationError, match="Quantidade deve ser maior que zero"):
        GoodsReceipt.create(purchase_request_id=1, quantity=0)
