from datetime import datetime

from sqlalchemy.orm import Session

from src.config import settings
from src.domain.enums import (
    ReservationStatus,
    ServiceOrderStatus,
    StockWithdrawalStatus,
)
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.database import (
    ProductModel,
    ReservationModel,
    ServiceOrderModel,
    StockWithdrawalModel,
)
from src.infrastructure.email.service import send_email


class ExecutionService:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(self, service_order_id: int) -> ServiceOrderModel:
        os = self._get_os(service_order_id)
        if os.status != ServiceOrderStatus.AGUARDANDO_APROVACAO:
            raise ValidationError("OS deve estar aguardando aprovação para entrar na fila")
        os.status = ServiceOrderStatus.AGUARDANDO_APROVACAO
        self.db.commit()
        self.db.refresh(os)
        return os

    def start_service(self, service_order_id: int) -> ServiceOrderModel:
        os = self._get_os(service_order_id)
        if os.status not in (
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
            ServiceOrderStatus.EM_DIAGNOSTICO,
        ):
            raise ValidationError("OS não pode ser iniciada neste status")
        os.status = ServiceOrderStatus.EM_EXECUCAO
        os.started_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(os)
        return os

    def finish_service(self, service_order_id: int) -> ServiceOrderModel:
        os = self._get_os(service_order_id)
        if os.status != ServiceOrderStatus.EM_EXECUCAO:
            raise ValidationError("OS deve estar em execução para ser finalizada")
        os.status = ServiceOrderStatus.FINALIZADA
        os.finished_at = datetime.utcnow()

        for line in os.product_lines:
            product = self.db.query(ProductModel).filter(ProductModel.id == line.product_id).first()
            if product:
                product.stock_quantity -= line.quantity
            reservations = (
                self.db.query(ReservationModel)
                .filter(
                    ReservationModel.service_order_id == service_order_id,
                    ReservationModel.product_id == line.product_id,
                    ReservationModel.status == ReservationStatus.ACTIVE,
                )
                .all()
            )
            for res in reservations:
                res.status = ReservationStatus.CONSUMED

        self.db.commit()
        self.db.refresh(os)
        return os

    async def request_stock_withdrawal(
        self, service_order_id: int, product_id: int, quantity: int
    ) -> StockWithdrawalModel:
        os = self._get_os(service_order_id)
        withdrawal = StockWithdrawalModel(
            service_order_id=service_order_id,
            product_id=product_id,
            quantity=quantity,
        )
        self.db.add(withdrawal)
        self.db.commit()
        self.db.refresh(withdrawal)

        await send_email(
            settings.smtp_from,
            f"Retirada de estoque solicitada - OS #{service_order_id}",
            f"Retirada de {quantity} unidades do produto #{product_id} para OS #{service_order_id}",
        )
        return withdrawal

    def list_pending_withdrawals(self) -> list[StockWithdrawalModel]:
        return (
            self.db.query(StockWithdrawalModel)
            .filter(StockWithdrawalModel.status == StockWithdrawalStatus.PENDING)
            .all()
        )

    def list_os_with_withdrawals(self) -> list[ServiceOrderModel]:
        os_ids = (
            self.db.query(StockWithdrawalModel.service_order_id)
            .filter(StockWithdrawalModel.status == StockWithdrawalStatus.FULFILLED)
            .distinct()
            .all()
        )
        ids = [row[0] for row in os_ids]
        if not ids:
            return []
        return (
            self.db.query(ServiceOrderModel)
            .filter(
                ServiceOrderModel.id.in_(ids),
                ServiceOrderModel.status == ServiceOrderStatus.EM_EXECUCAO,
            )
            .all()
        )

    def _get_os(self, service_order_id: int) -> ServiceOrderModel:
        os = self.db.query(ServiceOrderModel).filter(ServiceOrderModel.id == service_order_id).first()
        if not os:
            raise NotFoundError("OS não encontrada")
        return os
