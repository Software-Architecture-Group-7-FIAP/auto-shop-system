from dataclasses import replace
from datetime import datetime

import pytest

from src.application.services.execution_service import ExecutionService
from src.domain.enums import ServiceOrderStatus, StockWithdrawalStatus
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.execution.entity import StockWithdrawal
from src.domain.service_order.entity import ServiceOrder, ServiceOrderProductLine


class InMemoryServiceOrderRepository:
    def __init__(self, service_orders: list[ServiceOrder] | None = None):
        self.service_orders = {
            service_order.id: service_order
            for service_order in service_orders or []
            if service_order.id is not None
        }

    def get_by_id(self, service_order_id: int) -> ServiceOrder | None:
        return self.service_orders.get(service_order_id)

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrder]:
        orders = list(self.service_orders.values())
        if status:
            return [order for order in orders if order.status == status]
        return orders

    def list_with_execution_times(self) -> list[ServiceOrder]:
        return []

    def list_by_ids_and_status(
        self,
        service_order_ids: list[int],
        status: ServiceOrderStatus,
    ) -> list[ServiceOrder]:
        return [
            service_order
            for service_order in self.service_orders.values()
            if service_order.id in service_order_ids and service_order.status == status
        ]

    def save(self, service_order: ServiceOrder) -> ServiceOrder:
        assert service_order.id is not None
        self.service_orders[service_order.id] = service_order
        return service_order


class InMemoryStockWithdrawalRepository:
    def __init__(self, withdrawals: list[StockWithdrawal] | None = None):
        self.withdrawals = {
            withdrawal.id: withdrawal
            for withdrawal in withdrawals or []
            if withdrawal.id is not None
        }
        self.next_id = 1

    def add(self, withdrawal: StockWithdrawal) -> StockWithdrawal:
        created = replace(withdrawal, id=self.next_id)
        self.withdrawals[created.id] = created
        self.next_id += 1
        return created

    def list_pending(self) -> list[StockWithdrawal]:
        return [
            withdrawal
            for withdrawal in self.withdrawals.values()
            if withdrawal.status == StockWithdrawalStatus.PENDING
        ]

    def list_fulfilled_service_order_ids(self) -> list[int]:
        return sorted(
            {
                withdrawal.service_order_id
                for withdrawal in self.withdrawals.values()
                if withdrawal.status == StockWithdrawalStatus.FULFILLED
            }
        )


class FakeProductGateway:
    def __init__(self):
        self.decrements: list[tuple[int, int]] = []

    def decrement_stock(self, product_id: int, quantity: int) -> None:
        self.decrements.append((product_id, quantity))


class FakeReservationGateway:
    def __init__(self):
        self.consumed: list[tuple[int, int]] = []

    def consume_active_for_product(self, service_order_id: int, product_id: int) -> None:
        self.consumed.append((service_order_id, product_id))


class FakeClock:
    def __init__(self, value: datetime):
        self.value = value

    def now(self) -> datetime:
        return self.value


class FakeRecipient:
    def stock_withdrawal_recipient(self) -> str:
        return "stock@test.com"


class FakeEmailSender:
    def __init__(self):
        self.messages = []

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        self.messages.append(
            {"to": to, "subject": subject, "body": body, "html": html}
        )


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def make_service_order(**overrides) -> ServiceOrder:
    base = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
        product_lines=[
            ServiceOrderProductLine(
                id=1,
                service_order_id=1,
                product_id=10,
                quantity=2,
                unit_price=5.0,
            )
        ],
    )
    return replace(base, **overrides)


def make_service(
    service_orders: InMemoryServiceOrderRepository | None = None,
    withdrawals: InMemoryStockWithdrawalRepository | None = None,
    products: FakeProductGateway | None = None,
    reservations: FakeReservationGateway | None = None,
    emails: FakeEmailSender | None = None,
    uow: FakeUnitOfWork | None = None,
) -> ExecutionService:
    return ExecutionService(
        service_orders=service_orders
        or InMemoryServiceOrderRepository([make_service_order()]),
        withdrawals=withdrawals or InMemoryStockWithdrawalRepository(),
        products=products or FakeProductGateway(),
        reservations=reservations or FakeReservationGateway(),
        clock=FakeClock(datetime(2026, 1, 1, 8, 0, 0)),
        recipients=FakeRecipient(),
        emails=emails or FakeEmailSender(),
        uow=uow or FakeUnitOfWork(),
    )


def test_execution_service_starts_service_order_without_sqlalchemy():
    repository = InMemoryServiceOrderRepository([make_service_order()])
    uow = FakeUnitOfWork()
    service = make_service(service_orders=repository, uow=uow)

    updated = service.start_service(1)

    assert updated.status == ServiceOrderStatus.EM_EXECUCAO
    assert updated.started_at == datetime(2026, 1, 1, 8, 0, 0)
    assert repository.get_by_id(1).status == ServiceOrderStatus.EM_EXECUCAO
    assert uow.commits == 1


def test_execution_service_rejects_missing_service_order():
    service = make_service(service_orders=InMemoryServiceOrderRepository())

    with pytest.raises(NotFoundError, match="OS não encontrada"):
        service.start_service(1)


def test_execution_service_rejects_invalid_start_status():
    service = make_service(
        service_orders=InMemoryServiceOrderRepository(
            [make_service_order(status=ServiceOrderStatus.FINALIZADA)]
        )
    )

    with pytest.raises(ValidationError, match="OS não pode ser iniciada neste status"):
        service.start_service(1)


def test_execution_service_finishes_order_and_consumes_inventory():
    products = FakeProductGateway()
    reservations = FakeReservationGateway()
    service = make_service(
        service_orders=InMemoryServiceOrderRepository(
            [make_service_order(status=ServiceOrderStatus.EM_EXECUCAO)]
        ),
        products=products,
        reservations=reservations,
    )

    updated = service.finish_service(1)

    assert updated.status == ServiceOrderStatus.FINALIZADA
    assert updated.finished_at == datetime(2026, 1, 1, 8, 0, 0)
    assert products.decrements == [(10, 2)]
    assert reservations.consumed == [(1, 10)]


@pytest.mark.asyncio
async def test_execution_service_requests_stock_withdrawal_and_sends_email():
    withdrawals = InMemoryStockWithdrawalRepository()
    emails = FakeEmailSender()
    uow = FakeUnitOfWork()
    service = make_service(withdrawals=withdrawals, emails=emails, uow=uow)

    withdrawal = await service.request_stock_withdrawal(1, 10, 2)

    assert withdrawal.id == 1
    assert withdrawal.status == StockWithdrawalStatus.PENDING
    assert emails.messages == [
        {
            "to": "stock@test.com",
            "subject": "Retirada de estoque solicitada - OS #1",
            "body": "Retirada de 2 unidades do produto #10 para OS #1",
            "html": None,
        }
    ]
    assert uow.commits == 1


def test_execution_service_lists_orders_with_fulfilled_withdrawals():
    service = make_service(
        service_orders=InMemoryServiceOrderRepository(
            [
                make_service_order(id=1, status=ServiceOrderStatus.EM_EXECUCAO),
                make_service_order(id=2, status=ServiceOrderStatus.FINALIZADA),
            ]
        ),
        withdrawals=InMemoryStockWithdrawalRepository(
            [
                StockWithdrawal(
                    id=1,
                    service_order_id=1,
                    product_id=10,
                    quantity=2,
                    status=StockWithdrawalStatus.FULFILLED,
                ),
                StockWithdrawal(
                    id=2,
                    service_order_id=2,
                    product_id=10,
                    quantity=2,
                    status=StockWithdrawalStatus.FULFILLED,
                ),
            ]
        ),
    )

    assert [order.id for order in service.list_os_with_withdrawals()] == [1]
