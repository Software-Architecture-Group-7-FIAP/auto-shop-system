from src.application.ports.execution import (
    ExecutionClock,
    ExecutionEmailSender,
    ExecutionNotificationRecipient,
    ExecutionProductGateway,
    ExecutionReservationGateway,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import NotFoundError
from src.domain.execution.entity import (
    StockWithdrawal,
    enqueue_service_order,
    finish_service_order,
    start_service_order,
)
from src.domain.execution.repository import StockWithdrawalRepository
from src.domain.service_order.entity import ServiceOrder
from src.domain.service_order.repository import ServiceOrderRepository


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
    ):
        self.service_orders = service_orders
        self.withdrawals = withdrawals
        self.products = products
        self.reservations = reservations
        self.clock = clock
        self.recipients = recipients
        self.emails = emails
        self.uow = uow

    def enqueue(self, service_order_id: int) -> ServiceOrder:
        service_order = self._get_os(service_order_id)
        enqueue_service_order(service_order)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def start_service(self, service_order_id: int) -> ServiceOrder:
        service_order = self._get_os(service_order_id)
        start_service_order(service_order, self.clock.now())
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def finish_service(self, service_order_id: int) -> ServiceOrder:
        service_order = self._get_os(service_order_id)
        finish_service_order(service_order, self.clock.now())

        for line in service_order.product_lines:
            self.products.decrement_stock(line.product_id, line.quantity)
            self.reservations.consume_active_for_product(
                service_order_id,
                line.product_id,
            )

        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    async def request_stock_withdrawal(
        self, service_order_id: int, product_id: int, quantity: int
    ) -> StockWithdrawal:
        self._get_os(service_order_id)
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

    def _get_os(self, service_order_id: int) -> ServiceOrder:
        service_order = self.service_orders.get_by_id(service_order_id)
        if not service_order:
            raise NotFoundError("OS não encontrada")
        return service_order
