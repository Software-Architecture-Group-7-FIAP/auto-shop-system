from sqlalchemy.orm import Session

from src.application.ports.inventory import (
    InventoryProduct,
    InventoryServiceOrderProductLine,
)
from src.domain.enums import PurchaseRequestStatus, ReservationStatus
from src.domain.exceptions import NotFoundError
from src.domain.inventory.entity import GoodsReceipt, PurchaseRequest, Reservation
from src.infrastructure.database import (
    GoodsReceiptModel,
    ProductModel,
    PurchaseRequestModel,
    ReservationModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
)


class SqlAlchemyInventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_reservation(self, reservation: Reservation) -> Reservation:
        model = ReservationModel(
            service_order_id=reservation.service_order_id,
            product_id=reservation.product_id,
            quantity=reservation.quantity,
            status=reservation.status,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._reservation_to_domain(model)

    def list_active_reservations_for_service_order(
        self,
        service_order_id: int,
    ) -> list[Reservation]:
        models = (
            self.db.query(ReservationModel)
            .filter(
                ReservationModel.service_order_id == service_order_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .all()
        )
        return [self._reservation_to_domain(model) for model in models]

    def list_reservations(self) -> list[Reservation]:
        return [
            self._reservation_to_domain(model)
            for model in self.db.query(ReservationModel).all()
        ]

    def active_quantity_for_product(self, product_id: int) -> int:
        rows = (
            self.db.query(ReservationModel.quantity)
            .filter(
                ReservationModel.product_id == product_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .all()
        )
        return sum(row[0] for row in rows)

    def add_purchase_request(
        self,
        purchase_request: PurchaseRequest,
    ) -> PurchaseRequest:
        model = PurchaseRequestModel(
            product_id=purchase_request.product_id,
            supplier_id=purchase_request.supplier_id,
            service_order_id=purchase_request.service_order_id,
            quantity=purchase_request.quantity,
            status=purchase_request.status,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._purchase_request_to_domain(model)

    def get_purchase_request(self, purchase_request_id: int) -> PurchaseRequest | None:
        model = (
            self.db.query(PurchaseRequestModel)
            .filter(PurchaseRequestModel.id == purchase_request_id)
            .first()
        )
        if not model:
            return None
        return self._purchase_request_to_domain(model)

    def save_purchase_request(
        self,
        purchase_request: PurchaseRequest,
    ) -> PurchaseRequest:
        if purchase_request.id is None:
            raise NotFoundError("Solicitação de compra não encontrada")
        model = (
            self.db.query(PurchaseRequestModel)
            .filter(PurchaseRequestModel.id == purchase_request.id)
            .first()
        )
        if not model:
            raise NotFoundError("Solicitação de compra não encontrada")

        model.status = purchase_request.status
        model.quantity = purchase_request.quantity
        model.supplier_id = purchase_request.supplier_id
        model.service_order_id = purchase_request.service_order_id
        self.db.flush()
        self.db.refresh(model)
        return self._purchase_request_to_domain(model)

    def list_purchase_requests(self) -> list[PurchaseRequest]:
        return [
            self._purchase_request_to_domain(model)
            for model in self.db.query(PurchaseRequestModel).all()
        ]

    def has_pending_receipt(self, product_id: int) -> bool:
        return (
            self.db.query(PurchaseRequestModel)
            .filter(
                PurchaseRequestModel.product_id == product_id,
                PurchaseRequestModel.status.in_(
                    [PurchaseRequestStatus.PENDING, PurchaseRequestStatus.ORDERED]
                ),
            )
            .first()
            is not None
        )

    def get_pending_receipts(self, product_id: int) -> list[PurchaseRequest]:
        models = (
            self.db.query(PurchaseRequestModel)
            .filter(
                PurchaseRequestModel.product_id == product_id,
                PurchaseRequestModel.status.in_(
                    [PurchaseRequestStatus.PENDING, PurchaseRequestStatus.ORDERED]
                ),
            )
            .all()
        )
        return [self._purchase_request_to_domain(model) for model in models]

    def add_receipt(self, receipt: GoodsReceipt) -> GoodsReceipt:
        model = GoodsReceiptModel(
            purchase_request_id=receipt.purchase_request_id,
            quantity=receipt.quantity,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._receipt_to_domain(model)

    @staticmethod
    def _reservation_to_domain(model: ReservationModel) -> Reservation:
        return Reservation(
            id=model.id,
            service_order_id=model.service_order_id,
            product_id=model.product_id,
            quantity=model.quantity,
            status=model.status,
            created_at=model.created_at,
        )

    @staticmethod
    def _purchase_request_to_domain(model: PurchaseRequestModel) -> PurchaseRequest:
        return PurchaseRequest(
            id=model.id,
            product_id=model.product_id,
            supplier_id=model.supplier_id,
            service_order_id=model.service_order_id,
            quantity=model.quantity,
            status=model.status,
            created_at=model.created_at,
        )

    @staticmethod
    def _receipt_to_domain(model: GoodsReceiptModel) -> GoodsReceipt:
        return GoodsReceipt(
            id=model.id,
            purchase_request_id=model.purchase_request_id,
            quantity=model.quantity,
            received_at=model.received_at,
        )


class SqlAlchemyInventoryProductGateway:
    def __init__(self, db: Session):
        self.db = db

    def get_product(self, product_id: int) -> InventoryProduct | None:
        model = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not model:
            return None
        return InventoryProduct(
            id=model.id,
            stock_quantity=model.stock_quantity,
            supplier_id=model.supplier_id,
        )

    def get_product_for_update(self, product_id: int) -> InventoryProduct | None:
        model = (
            self.db.query(ProductModel)
            .filter(ProductModel.id == product_id)
            .with_for_update()
            .first()
        )
        if not model:
            return None
        return InventoryProduct(
            id=model.id,
            stock_quantity=model.stock_quantity,
            supplier_id=model.supplier_id,
        )

    def add_stock(self, product_id: int, quantity: int) -> None:
        model = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if model:
            model.stock_quantity += quantity
            self.db.flush()


class SqlAlchemyInventoryServiceOrderLookup:
    def __init__(self, db: Session):
        self.db = db

    def get_product_lines(
        self,
        service_order_id: int,
    ) -> list[InventoryServiceOrderProductLine] | None:
        service_order = (
            self.db.query(ServiceOrderModel)
            .filter(ServiceOrderModel.id == service_order_id)
            .first()
        )
        if not service_order:
            return None

        models = (
            self.db.query(ServiceOrderProductLineModel)
            .filter(ServiceOrderProductLineModel.service_order_id == service_order_id)
            .all()
        )
        return [
            InventoryServiceOrderProductLine(
                product_id=model.product_id,
                quantity=model.quantity,
            )
            for model in models
        ]
