from typing import Protocol

from src.domain.enums import ServiceOrderStatus
from src.domain.pagination import Page
from src.domain.service_order.entity import ServiceOrder
from src.domain.service_order.rules import ServiceOrderListQuery


class ServiceOrderRepository(Protocol):
    def get_by_id(self, service_order_id: int) -> ServiceOrder | None:
        ...

    def get_by_tracking_token_fingerprint(self, token_fingerprint: str) -> ServiceOrder | None:
        ...

    def set_tracking_token_fingerprint(
        self,
        service_order_id: int,
        token_fingerprint: str,
    ) -> None:
        ...

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrder]:
        ...

    def list_operational(self, query: ServiceOrderListQuery) -> Page[ServiceOrder]:
        ...

    def list_with_execution_times(self) -> list[ServiceOrder]:
        ...

    def list_by_ids_and_status(
        self,
        service_order_ids: list[int],
        status: ServiceOrderStatus,
    ) -> list[ServiceOrder]:
        ...

    def save(self, service_order: ServiceOrder) -> ServiceOrder:
        ...
