from typing import Protocol

from src.domain.enums import ServiceOrderStatus
from src.domain.service_order.entity import ServiceOrder


class ServiceOrderRepository(Protocol):
    def get_by_id(self, service_order_id: int) -> ServiceOrder | None:
        ...

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrder]:
        ...

    def list_with_execution_times(self) -> list[ServiceOrder]:
        ...

    def save(self, service_order: ServiceOrder) -> ServiceOrder:
        ...
