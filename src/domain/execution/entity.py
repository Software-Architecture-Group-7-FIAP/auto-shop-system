from dataclasses import dataclass
from datetime import datetime

from src.domain.enums import ServiceOrderStatus, StockWithdrawalStatus
from src.domain.exceptions import ValidationError
from src.domain.service_order.entity import ServiceOrder


@dataclass
class StockWithdrawal:
    id: int | None
    service_order_id: int
    product_id: int
    quantity: int
    status: StockWithdrawalStatus = StockWithdrawalStatus.PENDING
    requested_at: datetime | None = None
    fulfilled_at: datetime | None = None

    @classmethod
    def create(
        cls,
        service_order_id: int,
        product_id: int,
        quantity: int,
    ) -> "StockWithdrawal":
        if quantity <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")
        return cls(
            id=None,
            service_order_id=service_order_id,
            product_id=product_id,
            quantity=quantity,
        )


def enqueue_service_order(service_order: ServiceOrder) -> None:
    if service_order.status != ServiceOrderStatus.AGUARDANDO_APROVACAO:
        raise ValidationError("OS deve estar aguardando aprovação para entrar na fila")
    service_order.status = ServiceOrderStatus.AGUARDANDO_APROVACAO


def start_service_order(service_order: ServiceOrder, started_at: datetime) -> None:
    if service_order.status not in (
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.EM_DIAGNOSTICO,
    ):
        raise ValidationError("OS não pode ser iniciada neste status")
    service_order.status = ServiceOrderStatus.EM_EXECUCAO
    service_order.started_at = started_at


def finish_service_order(service_order: ServiceOrder, finished_at: datetime) -> None:
    if service_order.status != ServiceOrderStatus.EM_EXECUCAO:
        raise ValidationError("OS deve estar em execução para ser finalizada")
    service_order.status = ServiceOrderStatus.FINALIZADA
    service_order.finished_at = finished_at
