from dataclasses import dataclass, field
from datetime import datetime

from src.domain.enums import Priority, ServiceOrderStatus
from src.domain.exceptions import ValidationError


@dataclass
class ServiceOrderServiceLine:
    id: int | None
    service_order_id: int | None
    service_id: int
    quantity: int
    unit_price: float


@dataclass
class ServiceOrderProductLine:
    id: int | None
    service_order_id: int | None
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

    @classmethod
    def open(
        cls,
        customer_id: int,
        vehicle_id: int,
        service_lines: list[ServiceOrderServiceLine],
        product_lines: list[ServiceOrderProductLine],
    ) -> "ServiceOrder":
        merged_service_lines = cls._merge_service_lines(service_lines)
        merged_product_lines = cls._merge_product_lines(product_lines)
        if not merged_service_lines and not merged_product_lines:
            raise ValidationError("Ao menos um serviço ou produto deve ser informado")
        return cls(
            id=None,
            budget_id=None,
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            status=ServiceOrderStatus.RECEBIDA,
            priority=Priority.NORMAL,
            mechanic_name=None,
            total_price=cls._calculate_total(merged_service_lines, merged_product_lines),
            service_lines=merged_service_lines,
            product_lines=merged_product_lines,
        )

    @classmethod
    def _merge_service_lines(
        cls,
        lines: list[ServiceOrderServiceLine],
    ) -> list[ServiceOrderServiceLine]:
        merged: dict[int, ServiceOrderServiceLine] = {}
        for line in lines:
            cls._validate_quantity(line.quantity)
            existing = merged.get(line.service_id)
            if existing is None:
                merged[line.service_id] = line
            else:
                existing.quantity += line.quantity
        return list(merged.values())

    @classmethod
    def _merge_product_lines(
        cls,
        lines: list[ServiceOrderProductLine],
    ) -> list[ServiceOrderProductLine]:
        merged: dict[int, ServiceOrderProductLine] = {}
        for line in lines:
            cls._validate_quantity(line.quantity)
            existing = merged.get(line.product_id)
            if existing is None:
                merged[line.product_id] = line
            else:
                existing.quantity += line.quantity
        return list(merged.values())

    @staticmethod
    def _calculate_total(
        service_lines: list[ServiceOrderServiceLine],
        product_lines: list[ServiceOrderProductLine],
    ) -> float:
        service_total = sum(line.unit_price * line.quantity for line in service_lines)
        product_total = sum(line.unit_price * line.quantity for line in product_lines)
        return service_total + product_total

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if quantity <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")

    def assign_mechanic(self, mechanic_name: str) -> None:
        cleaned_name = mechanic_name.strip()
        if not cleaned_name:
            raise ValidationError("Nome do mecânico é obrigatório")
        self.mechanic_name = cleaned_name
        self.status = ServiceOrderStatus.EM_DIAGNOSTICO

    def set_priority(self, priority: Priority) -> None:
        self.priority = priority

    def override_status(self, status: ServiceOrderStatus, reason: str) -> None:
        if not reason.strip():
            raise ValidationError("Motivo da alteração de status é obrigatório")
        self.status = status

    def mark_delivered(self) -> None:
        if self.status != ServiceOrderStatus.FINALIZADA:
            raise ValidationError("OS deve estar finalizada para ser entregue")
        self.status = ServiceOrderStatus.ENTREGUE
