from dataclasses import dataclass, field
from datetime import datetime

from src.domain.enums import Priority, ServiceOrderStatus


@dataclass
class ServiceOrderServiceLine:
    id: int | None
    service_order_id: int
    service_id: int
    quantity: int
    unit_price: float


@dataclass
class ServiceOrderProductLine:
    id: int | None
    service_order_id: int
    product_id: int
    quantity: int
    unit_price: float


@dataclass
class ServiceOrder:
    id: int | None
    budget_id: int | None
    customer_id: int
    vehicle_id: int
    status: ServiceOrderStatus = ServiceOrderStatus.RECEBIDA
    priority: Priority = Priority.NORMAL
    mechanic_name: str | None = None
    total_price: float = 0.0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    service_lines: list[ServiceOrderServiceLine] = field(default_factory=list)
    product_lines: list[ServiceOrderProductLine] = field(default_factory=list)

    def assign_mechanic(self, mechanic_name: str) -> None:
        self.mechanic_name = mechanic_name
        self.status = ServiceOrderStatus.EM_DIAGNOSTICO

    def set_priority(self, priority: Priority) -> None:
        self.priority = priority

    def mark_delivered(self) -> None:
        self.status = ServiceOrderStatus.ENTREGUE
