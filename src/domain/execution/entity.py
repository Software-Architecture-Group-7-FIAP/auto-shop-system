from dataclasses import dataclass
from datetime import datetime

from src.domain.enums import Priority, ServiceOrderStatus, StockWithdrawalStatus
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

    def fulfill(self, fulfilled_at: datetime) -> None:
        if self.status != StockWithdrawalStatus.PENDING:
            raise ValidationError("Solicitação de retirada já foi atendida ou cancelada")
        self.status = StockWithdrawalStatus.FULFILLED
        self.fulfilled_at = fulfilled_at


_QUEUE_PRIORITY_RANK = {
    Priority.URGENT: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
}


def order_execution_queue(service_orders: list[ServiceOrder]) -> list[ServiceOrder]:
    return sorted(
        service_orders,
        key=lambda so: (_QUEUE_PRIORITY_RANK[so.priority], so.created_at or datetime.max),
    )


def validate_withdrawal_quantity(
    service_order: ServiceOrder,
    product_id: int,
    quantity: int,
    already_requested: int,
) -> None:
    if service_order.status != ServiceOrderStatus.EM_EXECUCAO:
        raise ValidationError("Retirada de estoque só é permitida para OS em execução")

    required = sum(
        line.quantity
        for line in service_order.product_lines
        if line.product_id == product_id
    )
    if required == 0:
        raise ValidationError(
            f"Produto #{product_id} não está no escopo da OS #{service_order.id}"
        )
    if already_requested + quantity > required:
        raise ValidationError(
            f"Quantidade solicitada ({already_requested + quantity}) excede o total "
            f"necessário ({required}) para o produto #{product_id}"
        )


def enqueue_service_order(
    service_order: ServiceOrder,
    *,
    actor_id: int | None = None,
    request_id: str | None = None,
) -> None:
    service_order.record_queue_entry(actor_id=actor_id, request_id=request_id)


def start_service_order(
    service_order: ServiceOrder,
    started_at: datetime,
    *,
    actor_id: int | None = None,
    request_id: str | None = None,
) -> None:
    try:
        service_order.start_execution(started_at, actor_id=actor_id, request_id=request_id)
    except ValidationError:
        # Keep the public error used by the execution use case stable while the
        # aggregate owns the transition matrix.
        if service_order.status != ServiceOrderStatus.AGUARDANDO_INICIO:
            raise ValidationError("OS não pode ser iniciada neste status")
        raise


def finish_service_order(
    service_order: ServiceOrder,
    finished_at: datetime,
    withdrawn_quantities: dict[int, int],
    *,
    actor_id: int | None = None,
    request_id: str | None = None,
) -> None:
    if service_order.status != ServiceOrderStatus.EM_EXECUCAO:
        raise ValidationError("OS deve estar em execução para ser finalizada")

    required_by_product: dict[int, int] = {}
    for line in service_order.product_lines:
        required_by_product[line.product_id] = (
            required_by_product.get(line.product_id, 0) + line.quantity
        )

    pending_products = [
        product_id
        for product_id, required in required_by_product.items()
        if withdrawn_quantities.get(product_id, 0) < required
    ]
    if pending_products:
        raise ValidationError(
            "OS possui itens reservados sem retirada de estoque confirmada: "
            f"{pending_products}"
        )

    service_order.finish_execution(finished_at, actor_id=actor_id, request_id=request_id)
