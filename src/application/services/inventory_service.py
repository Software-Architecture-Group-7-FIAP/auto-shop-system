from sqlalchemy.orm import Session

from src.domain.enums import PurchaseRequestStatus, ReservationStatus
from src.domain.exceptions import NotFoundError
from src.infrastructure.database import (
    GoodsReceiptModel,
    ProductModel,
    PurchaseRequestModel,
    ReservationModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
)


class InventoryService:
    def __init__(self, db: Session):
        self.db = db

    def create_reservation(self, service_order_id: int, product_id: int, quantity: int) -> ReservationModel:
        reservation = ReservationModel(
            service_order_id=service_order_id,
            product_id=product_id,
            quantity=quantity,
        )
        self.db.add(reservation)
        self.db.commit()
        self.db.refresh(reservation)
        return reservation

    def create_reservations_for_os(self, service_order_id: int) -> list[ReservationModel]:
        os = self.db.query(ServiceOrderModel).filter(ServiceOrderModel.id == service_order_id).first()
        if not os:
            raise NotFoundError("OS não encontrada")
        reservations = []
        for line in os.product_lines:
            product = self.db.query(ProductModel).filter(ProductModel.id == line.product_id).first()
            if not product:
                continue
            available = self._available_stock(product.id)
            if available < line.quantity:
                pending = self.check_pending_receipt(product.id)
                if not pending:
                    self.create_purchase_request(product.id, line.quantity - available, service_order_id)
            reservation = self.create_reservation(service_order_id, line.product_id, line.quantity)
            reservations.append(reservation)
        return reservations

    def _available_stock(self, product_id: int) -> int:
        product = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not product:
            return 0
        reserved = (
            self.db.query(ReservationModel)
            .filter(
                ReservationModel.product_id == product_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .all()
        )
        reserved_qty = sum(r.quantity for r in reserved)
        return product.stock_quantity - reserved_qty

    def check_pending_receipt(self, product_id: int) -> bool:
        pending = (
            self.db.query(PurchaseRequestModel)
            .filter(
                PurchaseRequestModel.product_id == product_id,
                PurchaseRequestModel.status.in_(
                    [PurchaseRequestStatus.PENDING, PurchaseRequestStatus.ORDERED]
                ),
            )
            .first()
        )
        return pending is not None

    def create_purchase_request(
        self, product_id: int, quantity: int, service_order_id: int | None = None
    ) -> PurchaseRequestModel:
        product = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not product:
            raise NotFoundError("Produto não encontrado")
        pr = PurchaseRequestModel(
            product_id=product_id,
            quantity=quantity,
            service_order_id=service_order_id,
            supplier_id=product.supplier_id,
        )
        self.db.add(pr)
        self.db.commit()
        self.db.refresh(pr)
        return pr

    def list_purchase_requests(self) -> list[PurchaseRequestModel]:
        return self.db.query(PurchaseRequestModel).all()

    def list_reservations(self) -> list[ReservationModel]:
        return self.db.query(ReservationModel).all()

    def register_receipt(self, purchase_request_id: int, quantity: int) -> GoodsReceiptModel:
        pr = (
            self.db.query(PurchaseRequestModel)
            .filter(PurchaseRequestModel.id == purchase_request_id)
            .first()
        )
        if not pr:
            raise NotFoundError("Solicitação de compra não encontrada")
        receipt = GoodsReceiptModel(purchase_request_id=purchase_request_id, quantity=quantity)
        product = self.db.query(ProductModel).filter(ProductModel.id == pr.product_id).first()
        if product:
            product.stock_quantity += quantity
        pr.status = PurchaseRequestStatus.RECEIVED
        self.db.add(receipt)
        self.db.commit()
        self.db.refresh(receipt)
        return receipt

    def get_pending_receipts(self, product_id: int) -> list[PurchaseRequestModel]:
        return (
            self.db.query(PurchaseRequestModel)
            .filter(
                PurchaseRequestModel.product_id == product_id,
                PurchaseRequestModel.status.in_(
                    [PurchaseRequestStatus.PENDING, PurchaseRequestStatus.ORDERED]
                ),
            )
            .all()
        )
