from sqlalchemy import func, update
from sqlalchemy.orm import Session

from src.domain.enums import ReservationStatus, StockWithdrawalStatus
from src.domain.exceptions import NotFoundError, ValidationError
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

    def get_by_id(self, withdrawal_id: int) -> StockWithdrawal | None:
        model = (
            self.db.query(StockWithdrawalModel)
            .filter(StockWithdrawalModel.id == withdrawal_id)
            .first()
        )
        if not model:
            return None
        return self._to_domain(model)

    def get_by_id_for_update(self, withdrawal_id: int) -> StockWithdrawal | None:
        model = (
            self.db.query(StockWithdrawalModel)
            .filter(StockWithdrawalModel.id == withdrawal_id)
            .with_for_update()
            .first()
        )
        return self._to_domain(model) if model else None

    def save(self, withdrawal: StockWithdrawal) -> StockWithdrawal:
        model = (
            self.db.query(StockWithdrawalModel)
            .filter(StockWithdrawalModel.id == withdrawal.id)
            .first()
        )
        model.status = withdrawal.status
        model.fulfilled_at = withdrawal.fulfilled_at
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

    def list_by_service_order_id(self, service_order_id: int) -> list[StockWithdrawal]:
        models = (
            self.db.query(StockWithdrawalModel)
            .filter(StockWithdrawalModel.service_order_id == service_order_id)
            .all()
        )
        return [self._to_domain(model) for model in models]

    def list_by_service_order_ids(
        self,
        service_order_ids: list[int],
    ) -> list[StockWithdrawal]:
        if not service_order_ids:
            return []
        models = (
            self.db.query(StockWithdrawalModel)
            .filter(StockWithdrawalModel.service_order_id.in_(service_order_ids))
            .all()
        )
        return [self._to_domain(model) for model in models]

    def fulfilled_quantity_by_product(self, service_order_id: int) -> dict[int, int]:
        rows = (
            self.db.query(
                StockWithdrawalModel.product_id,
                func.sum(StockWithdrawalModel.quantity),
            )
            .filter(
                StockWithdrawalModel.service_order_id == service_order_id,
                StockWithdrawalModel.status == StockWithdrawalStatus.FULFILLED,
            )
            .group_by(StockWithdrawalModel.product_id)
            .all()
        )
        return {product_id: int(total) for product_id, total in rows}

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
        result = self.db.execute(
            update(ProductModel)
            .where(
                ProductModel.id == product_id,
                ProductModel.stock_quantity >= quantity,
            )
            .values(stock_quantity=ProductModel.stock_quantity - quantity)
        )
        if result.rowcount == 0:
            exists = self.db.query(ProductModel.id).filter(ProductModel.id == product_id).first()
            if exists is None:
                raise NotFoundError("Produto não encontrado")
            raise ValidationError("Estoque insuficiente")
        self.db.flush()


class SqlAlchemyExecutionReservationGateway:
    def __init__(self, db: Session):
        self.db = db

    def active_quantity_for_product(self, service_order_id: int, product_id: int) -> int:
        return sum(
            row[0]
            for row in self.db.query(ReservationModel.quantity)
            .filter(
                ReservationModel.service_order_id == service_order_id,
                ReservationModel.product_id == product_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .with_for_update()
            .all()
        )

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

    def consume_for_withdrawal(
        self,
        service_order_id: int,
        product_id: int,
        quantity: int,
    ) -> None:
        model = (
            self.db.query(ReservationModel)
            .filter(
                ReservationModel.service_order_id == service_order_id,
                ReservationModel.product_id == product_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .with_for_update()
            .first()
        )
        if model is None or model.quantity < quantity:
            raise ValidationError("Quantidade solicitada excede a reserva ativa")
        if model.quantity == quantity:
            model.status = ReservationStatus.CONSUMED
        else:
            model.quantity -= quantity
        self.db.flush()

    def release_active_for_service_order(self, service_order_id: int) -> None:
        (
            self.db.query(ReservationModel)
            .filter(
                ReservationModel.service_order_id == service_order_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .update(
                {ReservationModel.status: ReservationStatus.RELEASED},
                synchronize_session=False,
            )
        )
        self.db.flush()

