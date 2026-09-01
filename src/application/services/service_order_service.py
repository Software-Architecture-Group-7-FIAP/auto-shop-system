from src.application.ports.service_order import ServiceOrderContactLookup
from src.application.ports.service_order_tracking import ServiceOrderTrackingTokenService
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.budget.repository import BudgetRepository
from src.domain.enums import BudgetStatus, Priority, ServiceOrderStatus
from src.domain.auth.entity import UserRole
from src.domain.exceptions import ForbiddenError, NotFoundError
from src.domain.pagination import Page
from src.domain.service_order.entity import ServiceOrder
from src.domain.service_order.repository import ServiceOrderRepository
from src.domain.service_order.rules import ServiceOrderListItem, ServiceOrderListQuery


class ServiceOrderService:
    def __init__(
        self,
        service_orders: ServiceOrderRepository,
        contacts: ServiceOrderContactLookup,
        tracking_tokens: ServiceOrderTrackingTokenService,
        uow: UnitOfWork,
        budgets: BudgetRepository | None = None,
    ):
        self.service_orders = service_orders
        self.contacts = contacts
        self.tracking_tokens = tracking_tokens
        self.uow = uow
        self.budgets = budgets

    def get_by_id(self, service_order_id: int) -> ServiceOrder:
        service_order = self.service_orders.get_by_id(service_order_id)
        if not service_order:
            raise NotFoundError("OS não encontrada")
        return service_order

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrder]:
        return self.service_orders.list_all(status)

    def list_operational(
        self,
        query: ServiceOrderListQuery,
    ) -> Page[ServiceOrderListItem]:
        return self.service_orders.list_operational(query)

    def get_by_tracking_token(self, token: str) -> ServiceOrder:
        token_fingerprint = self.tracking_tokens.fingerprint(token)
        service_order = self.service_orders.get_by_tracking_token_fingerprint(
            token_fingerprint
        )
        if not service_order:
            raise NotFoundError("Link de acompanhamento inválido")
        return service_order

    def assign_mechanic(
        self,
        service_order_id: int,
        mechanic_name: str,
        reason: str | None = None,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> ServiceOrder:
        service_order = self.get_by_id(service_order_id)
        service_order.assign_mechanic(
            mechanic_name,
            reason,
            actor_id=actor_id,
            request_id=request_id,
        )
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def update(
        self,
        service_order_id: int,
        mechanic_name: str | None = None,
        priority: Priority | None = None,
        mechanic_reason: str | None = None,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> ServiceOrder:
        service_order = self.get_by_id(service_order_id)
        if priority is not None:
            service_order.set_priority(priority)
        if mechanic_name is not None:
            service_order.assign_mechanic(
                mechanic_name,
                mechanic_reason,
                actor_id=actor_id,
                request_id=request_id,
            )
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def override_status(
        self,
        service_order_id: int,
        status: ServiceOrderStatus,
        reason: str,
        *,
        actor_role: UserRole | str | None = None,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> ServiceOrder:
        if actor_role not in (UserRole.ADMIN, UserRole.ADMIN.value):
            raise ForbiddenError("Apenas administradores podem usar o override de status")
        service_order = self.get_by_id(service_order_id)
        previous_status = service_order.status
        service_order.override_status(
            status,
            reason,
            actor_id=actor_id,
            request_id=request_id,
        )
        if (
            previous_status == ServiceOrderStatus.AGUARDANDO_APROVACAO
            and self.budgets is not None
            and service_order.budget_id is not None
        ):
            related = self.budgets.list_revision_family(service_order.budget_id)
            candidates = [
                budget for budget in related if budget.status == BudgetStatus.SENT
            ]
            for pending in sorted(candidates, key=lambda item: item.revision_number, reverse=True)[:1]:
                pending.supersede()
                self.budgets.save(pending)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def set_priority(self, service_order_id: int, priority: Priority) -> ServiceOrder:
        service_order = self.get_by_id(service_order_id)
        service_order.set_priority(priority)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def get_average_execution_time(self) -> dict:
        orders = self.service_orders.list_with_execution_times()
        if not orders:
            return {"average_hours": 0, "sample_size": 0}
        total_seconds = sum(
            (order.finished_at - order.started_at).total_seconds() for order in orders
        )
        avg_hours = total_seconds / len(orders) / 3600
        return {"average_hours": round(avg_hours, 2), "sample_size": len(orders)}
