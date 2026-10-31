from dataclasses import dataclass
import logging
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID, uuid4

from src.application.ports.execution import (
    ExecutionClock,
    ExecutionEmailSender,
    ExecutionNotificationRecipient,
    ExecutionProductGateway,
    ExecutionReservationGateway,
)
from src.application.ports.events import (
    ServiceOrderEventPublisher,
    ServiceOrderProcessingFailed,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.enums import ServiceOrderStatus, StockWithdrawalStatus
from src.domain.exceptions import DomainError, NotFoundError, ValidationError
from src.domain.execution.entity import (
    StockWithdrawal,
    enqueue_service_order,
    finish_service_order,
    order_execution_queue,
    start_service_order,
    validate_withdrawal_quantity,
)
from src.domain.execution.repository import StockWithdrawalRepository
from src.domain.service_order.entity import ServiceOrder
from src.domain.service_order.repository import ServiceOrderRepository


logger = logging.getLogger(__name__)


@dataclass
class ServiceOrderWithdrawalDetail:
    service_order: ServiceOrder
    withdrawals: list[StockWithdrawal]


class ExecutionService:
    def __init__(
        self,
        service_orders: ServiceOrderRepository,
        withdrawals: StockWithdrawalRepository,
        products: ExecutionProductGateway,
        reservations: ExecutionReservationGateway,
        clock: ExecutionClock,
        recipients: ExecutionNotificationRecipient,
        emails: ExecutionEmailSender,
        uow: UnitOfWork,
        event_publisher: ServiceOrderEventPublisher | None = None,
    ):
        self.service_orders = service_orders
        self.withdrawals = withdrawals
        self.products = products
        self.reservations = reservations
        self.clock = clock
        self.recipients = recipients
        self.emails = emails
        self.uow = uow
        self.event_publisher = event_publisher

    def enqueue(self, service_order_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> ServiceOrder:
        correlation_id = self._normalize_request_id(request_id)
        return self._run_monitored(
            service_order_id,
            correlation_id,
            lambda: self._enqueue(service_order_id, actor_id, correlation_id),
        )

    def _enqueue(
        self,
        service_order_id: int,
        actor_id: int | None,
        request_id: str,
    ) -> ServiceOrder:
        service_order = self._get_os(service_order_id)
        enqueue_service_order(service_order, actor_id=actor_id, request_id=request_id)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def start_service(self, service_order_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> ServiceOrder:
        correlation_id = self._normalize_request_id(request_id)
        return self._run_monitored(
            service_order_id,
            correlation_id,
            lambda: self._start_service(service_order_id, actor_id, correlation_id),
        )

    def _start_service(
        self,
        service_order_id: int,
        actor_id: int | None,
        request_id: str,
    ) -> ServiceOrder:
        service_order = self._get_os(service_order_id)
        service_order.ensure_can_start_execution()
        required_by_product: dict[int, int] = {}
        for line in service_order.product_lines:
            required_by_product[line.product_id] = (
                required_by_product.get(line.product_id, 0) + line.quantity
            )
        for product_id, required_quantity in required_by_product.items():
            if self.reservations.active_quantity_for_product(
                service_order_id, product_id
            ) < required_quantity:
                raise ValidationError(
                    f"Estoque não reservado para o produto #{product_id}"
                )
        start_service_order(service_order, self.clock.now(), actor_id=actor_id, request_id=request_id)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def list_execution_queue(self) -> list[ServiceOrder]:
        waiting = self.service_orders.list_all(ServiceOrderStatus.AGUARDANDO_INICIO)
        return order_execution_queue(waiting)

    def finish_service(self, service_order_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> ServiceOrder:
        correlation_id = self._normalize_request_id(request_id)
        return self._run_monitored(
            service_order_id,
            correlation_id,
            lambda: self._finish_service(service_order_id, actor_id, correlation_id),
        )

    def _finish_service(
        self,
        service_order_id: int,
        actor_id: int | None,
        request_id: str,
    ) -> ServiceOrder:
        service_order = self._get_os(service_order_id)
        withdrawn = self.withdrawals.fulfilled_quantity_by_product(service_order_id)
        finish_service_order(service_order, self.clock.now(), withdrawn, actor_id=actor_id, request_id=request_id)

        self.reservations.release_active_for_service_order(service_order_id)

        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def _run_monitored(
        self,
        service_order_id: int,
        request_id: str,
        operation: Callable[[], ServiceOrder],
    ) -> ServiceOrder:
        try:
            return operation()
        except DomainError:
            raise
        except Exception:
            self._report_processing_failure(service_order_id, request_id)
            raise

    @staticmethod
    def _normalize_request_id(request_id: str | None) -> str:
        if request_id:
            try:
                return str(UUID(request_id.strip()))
            except (AttributeError, ValueError):
                pass
        return str(uuid4())

    def _report_processing_failure(
        self,
        service_order_id: int,
        request_id: str,
    ) -> None:
        event = ServiceOrderProcessingFailed(
            event_id=str(uuid4()),
            occurred_at=datetime.now(timezone.utc),
            request_id=request_id,
            service_order_id=service_order_id,
        )
        try:
            self.uow.rollback()
        except Exception:
            logger.error(
                "service_order_processing_rollback_failed event_id=%s request_id=%s service_order_id=%s",
                event.event_id,
                event.request_id,
                event.service_order_id,
            )

        if self.event_publisher is None:
            logger.error(
                "service_order_failure_event_publish_failed event_id=%s request_id=%s service_order_id=%s reason=publisher_not_configured",
                event.event_id,
                event.request_id,
                event.service_order_id,
            )
            return

        try:
            self.event_publisher.publish(event)
        except Exception:
            logger.error(
                "service_order_failure_event_publish_failed event_id=%s request_id=%s service_order_id=%s",
                event.event_id,
                event.request_id,
                event.service_order_id,
            )
            return

        logger.error(
            "service_order_processing_failed event_id=%s request_id=%s service_order_id=%s event_type=%s",
            event.event_id,
            event.request_id,
            event.service_order_id,
            event.event_type,
        )

    async def request_stock_withdrawal(
        self, service_order_id: int, product_id: int, quantity: int
    ) -> StockWithdrawal:
        service_order = self._get_os(service_order_id)
        existing = self.withdrawals.list_by_service_order_id(service_order_id)
        already_requested = sum(
            w.quantity
            for w in existing
            if w.product_id == product_id and w.status != StockWithdrawalStatus.CANCELLED
        )
        validate_withdrawal_quantity(service_order, product_id, quantity, already_requested)

        withdrawal = self.withdrawals.add(
            StockWithdrawal.create(service_order_id, product_id, quantity)
        )
        await self.emails.send_email(
            self.recipients.stock_withdrawal_recipient(),
            f"Retirada de estoque solicitada - OS #{service_order_id}",
            f"Retirada de {quantity} unidades do produto #{product_id} para OS #{service_order_id}",
        )
        self.uow.commit()
        return withdrawal

    def fulfill_withdrawal(self, withdrawal_id: int) -> StockWithdrawal:
        get_for_update = getattr(self.withdrawals, "get_by_id_for_update", None)
        withdrawal = (
            get_for_update(withdrawal_id)
            if get_for_update is not None
            else self.withdrawals.get_by_id(withdrawal_id)
        )
        if not withdrawal:
            raise NotFoundError("Solicitação de retirada não encontrada")
        self.reservations.consume_for_withdrawal(
            withdrawal.service_order_id,
            withdrawal.product_id,
            withdrawal.quantity,
        )
        withdrawal.fulfill(self.clock.now())
        self.products.decrement_stock(withdrawal.product_id, withdrawal.quantity)
        updated = self.withdrawals.save(withdrawal)
        self.uow.commit()
        return updated

    def list_pending_withdrawals(self) -> list[StockWithdrawal]:
        return self.withdrawals.list_pending()

    def list_os_with_withdrawals(self) -> list[ServiceOrder]:
        ids = self.withdrawals.list_fulfilled_service_order_ids()
        if not ids:
            return []
        return self.service_orders.list_by_ids_and_status(
            ids,
            ServiceOrderStatus.EM_EXECUCAO,
        )

    def list_os_with_withdrawal_details(self) -> list[ServiceOrderWithdrawalDetail]:
        ids = self.withdrawals.list_fulfilled_service_order_ids()
        if not ids:
            return []
        orders = self.service_orders.list_by_ids_and_status(
            ids,
            ServiceOrderStatus.EM_EXECUCAO,
        )
        withdrawals = self.withdrawals.list_by_service_order_ids(
            [order.id for order in orders if order.id is not None]
        )
        withdrawals_by_order: dict[int, list[StockWithdrawal]] = {}
        for withdrawal in withdrawals:
            withdrawals_by_order.setdefault(withdrawal.service_order_id, []).append(
                withdrawal
            )
        return [
            ServiceOrderWithdrawalDetail(
                service_order=order,
                withdrawals=withdrawals_by_order.get(order.id or 0, []),
            )
            for order in orders
        ]

    def _get_os(self, service_order_id: int) -> ServiceOrder:
        service_order = self.service_orders.get_by_id(service_order_id)
        if not service_order:
            raise NotFoundError("OS não encontrada")
        return service_order
