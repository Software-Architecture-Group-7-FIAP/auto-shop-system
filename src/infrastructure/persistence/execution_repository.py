from sqlalchemy.orm import Session

from src.domain.enums import ReservationStatus, StockWithdrawalStatus
from src.domain.execution.entity import StockWithdrawal
from src.infrastructure.database import ProductModel, ReservationModel, StockWithdrawalModel


class SqlAlchemyStockWithdrawalRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, withdrawal: StockWithdrawal) -> StockWithdrawal:
        model = StockWithdrawalModel(
            service_order_id=withdrawal.service_order_id,
            product_id=withdrawal.product_id,
            quantity=withdrawal.quantity,
            status=withdrawal.status,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def list_pending(self) -> list[StockWithdrawal]:
        models = (
            self.db.query(StockWithdrawalModel)
            .filter(StockWithdrawalModel.status == StockWithdrawalStatus.PENDING)
            .all()
        )
        return [self._to_domain(model) for model in models]

    def list_fulfilled_service_order_ids(self) -> list[int]:
        rows = (
            self.db.query(StockWithdrawalModel.service_order_id)
            .filter(StockWithdrawalModel.status == StockWithdrawalStatus.FULFILLED)
            .distinct()
            .all()
        )
        return [row[0] for row in rows]

    @staticmethod
    def _to_domain(model: StockWithdrawalModel) -> StockWithdrawal:
        return StockWithdrawal(
            id=model.id,
            service_order_id=model.service_order_id,
            product_id=model.product_id,
            quantity=model.quantity,
            status=model.status,
            requested_at=model.requested_at,
            fulfilled_at=model.fulfilled_at,
        )


class SqlAlchemyExecutionProductGateway:
    def __init__(self, db: Session):
        self.db = db

    def decrement_stock(self, product_id: int, quantity: int) -> None:
        model = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if model:
            model.stock_quantity -= quantity
            self.db.flush()


class SqlAlchemyExecutionReservationGateway:
    def __init__(self, db: Session):
        self.db = db

    def consume_active_for_product(self, service_order_id: int, product_id: int) -> None:
        models = (
            self.db.query(ReservationModel)
            .filter(
                ReservationModel.service_order_id == service_order_id,
                ReservationModel.product_id == product_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .all()
        )
        for model in models:
            model.status = ReservationStatus.CONSUMED
        self.db.flush()
