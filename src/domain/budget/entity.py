from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.domain.enums import BudgetStatus
from src.domain.exceptions import ValidationError


@dataclass
class BudgetServiceLine:
    id: int | None
    budget_id: int
    service_id: int
    quantity: int
    unit_price: float

    @classmethod
    def create(
        cls,
        budget_id: int,
        service_id: int,
        quantity: int,
        unit_price: float,
    ) -> "BudgetServiceLine":
        return cls(
            id=None,
            budget_id=budget_id,
            service_id=service_id,
            quantity=cls._positive_quantity(quantity),
            unit_price=unit_price,
        )

    @staticmethod
    def _positive_quantity(quantity: int) -> int:
        if quantity <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")
        return quantity


@dataclass
class BudgetProductLine:
    id: int | None
    budget_id: int
    product_id: int
    quantity: int
    unit_price: float
    from_service: bool = False

    @classmethod
    def create(
        cls,
        budget_id: int,
        product_id: int,
        quantity: int,
        unit_price: float,
        from_service: bool,
    ) -> "BudgetProductLine":
        return cls(
            id=None,
            budget_id=budget_id,
            product_id=product_id,
            quantity=BudgetServiceLine._positive_quantity(quantity),
            unit_price=unit_price,
            from_service=from_service,
        )


@dataclass
class ProductAvailability:
    product_id: int
    product_name: str
    required: int
    available: int
    sufficient: bool

    def as_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "required": self.required,
            "available": self.available,
            "sufficient": self.sufficient,
        }


@dataclass
class Budget:
    id: int | None
    customer_id: int
    vehicle_id: int
    status: BudgetStatus = BudgetStatus.DRAFT
    total_price: float = 0.0
    estimated_delivery: datetime | None = None
    approval_token: str | None = None
    created_at: datetime | None = None
    service_lines: list[BudgetServiceLine] = field(default_factory=list)
    product_lines: list[BudgetProductLine] = field(default_factory=list)

    @classmethod
    def create(cls, customer_id: int, vehicle_id: int) -> "Budget":
        return cls(id=None, customer_id=customer_id, vehicle_id=vehicle_id)

    def add_service_line(
        self,
        service_id: int,
        quantity: int,
        unit_price: float,
    ) -> BudgetServiceLine:
        budget_id = self._required_id()
        return BudgetServiceLine.create(
            budget_id=budget_id,
            service_id=service_id,
            quantity=quantity,
            unit_price=unit_price,
        )

    def add_product_line(
        self,
        product_id: int,
        quantity: int,
        unit_price: float,
        from_service: bool,
    ) -> BudgetProductLine:
        budget_id = self._required_id()
        return BudgetProductLine.create(
            budget_id=budget_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            from_service=from_service,
        )

    def recalculate(
        self,
        service_hours: dict[int, float],
        now: datetime | None = None,
    ) -> None:
        self.total_price = sum(
            line.unit_price * line.quantity for line in self.service_lines
        ) + sum(line.unit_price * line.quantity for line in self.product_lines)

        total_hours = 0.0
        for line in self.service_lines:
            estimated_hours = service_hours.get(line.service_id)
            if estimated_hours is not None:
                total_hours += estimated_hours * line.quantity
        current_time = now or datetime.now(UTC).replace(tzinfo=None)
        self.estimated_delivery = current_time + timedelta(hours=max(total_hours, 1))

    def mark_sent(self, token: str) -> None:
        self.approval_token = token
        self.status = BudgetStatus.SENT

    def approve(self) -> None:
        if self.status == BudgetStatus.APPROVED:
            raise ValidationError("Orçamento já aprovado")
        self.status = BudgetStatus.APPROVED

    def reject(self) -> None:
        self.status = BudgetStatus.REJECTED

    def _required_id(self) -> int:
        if self.id is None:
            raise ValidationError("Orçamento precisa estar persistido")
        return self.id
