from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.domain.budget.value_objects import BudgetValidator
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
            quantity=quantity,
            unit_price=unit_price,
        )


@dataclass
class BudgetProductLine:
    id: int | None
    budget_id: int
    product_id: int
    quantity: int
    unit_price: float
    from_service: bool = False
    service_id: int | None = None

    @classmethod
    def create(
        cls,
        budget_id: int,
        product_id: int,
        quantity: int,
        unit_price: float,
        from_service: bool,
        service_id: int | None = None,
    ) -> "BudgetProductLine":
        return cls(
            id=None,
            budget_id=budget_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            from_service=from_service,
            service_id=service_id,
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

    def add_service_line(self, service_id: int, quantity: int, base_price: int, resolved_requirements: list[dict]) -> BudgetServiceLine:
        valid_quantity = BudgetValidator.ServiceLineValidator.validate_quantity(quantity)

        if any(line.service_id == service_id for line in self.service_lines):
            raise ValidationError("Este serviço já foi adicionado ao orçamento")

        return BudgetServiceLine(
            id=None,
            budget_id=self._required_id(),
            service_id=service_id,
            quantity=valid_quantity,
            unit_price=base_price,
        )
    
    def update_service_line(self, line_id: int, quantity: int) -> BudgetServiceLine:
        line = next((line for line in self.service_lines if line.id == line_id), None)
        if not line:
            raise ValidationError("Linha de serviço não encontrada")

        old_quantity = line.quantity
        valid_quantity = BudgetValidator.ServiceLineValidator.validate_quantity(quantity)
        line.quantity = valid_quantity

        if old_quantity != valid_quantity:
            quantity_factor = valid_quantity / old_quantity
            matching_product_lines = [
                product_line
                for product_line in self.product_lines
                if product_line.from_service and product_line.service_id == line.service_id
            ]
            fallback_product_lines = [
                product_line
                for product_line in self.product_lines
                if product_line.from_service and product_line.service_id is None
            ]
            target_product_lines = matching_product_lines or fallback_product_lines

            for product_line in target_product_lines:
                product_line.quantity = max(1, int(product_line.quantity * quantity_factor))

        return line

    def add_product_line(
        self,
        product_id: int,
        quantity: int,
        unit_price: float,
        from_service: bool,
        service_id: int | None = None,
    ) -> BudgetProductLine:
        valid_quantity = BudgetValidator.ProductLineValidator.validate_quantity(quantity)
        if not from_service and any(
            line.product_id == product_id and not line.from_service
            for line in self.product_lines
        ):
            raise ValidationError("Este produto já foi adicionado ao orçamento")
        return BudgetProductLine(
            id=None,
            budget_id=self._required_id(),
            product_id=product_id,
            quantity=valid_quantity,
            unit_price=unit_price,
            from_service=from_service,
            service_id=service_id,
        )

    def update_product_line(self, line_id: int, quantity: int) -> BudgetProductLine:
        line = next((line for line in self.product_lines if line.id == line_id), None)
        if not line:
            raise ValidationError("Linha de produto não encontrada")

        valid_quantity = BudgetValidator.ProductLineValidator.validate_quantity(quantity)
        line.quantity = valid_quantity
        return line

    def remove_service_line(
        self,
        line_id: int,
        service_requirements: list[dict] | None = None,
    ) -> tuple[BudgetServiceLine, list[BudgetProductLine]]:
        line = next((line for line in self.service_lines if line.id == line_id), None)
        if not line:
            raise ValidationError("Linha de serviço não encontrada")

        self.service_lines.remove(line)

        removed_product_lines: list[BudgetProductLine] = []
        for product_line in self.product_lines[:]:
            if product_line.from_service and product_line.service_id == line.service_id:
                self.product_lines.remove(product_line)
                removed_product_lines.append(product_line)

        return line, removed_product_lines

    def remove_product_line(self, line_id: int) -> BudgetProductLine:
        line = next((line for line in self.product_lines if line.id == line_id), None)
        if not line:
            raise ValidationError("Linha de produto não encontrada")

        self.product_lines.remove(line)
        return line

    def _derived_product_lines_for_service(
        self,
        service_line: BudgetServiceLine,
    ) -> list[BudgetProductLine]:
        derived_lines: list[BudgetProductLine] = []
        for product_line in self.product_lines:
            if product_line.from_service and product_line.service_id == service_line.service_id:
                derived_lines.append(product_line)
        return derived_lines

    def recalculate_estimated_delivery(
        self,
        service_hours: dict[int, float],
        now: datetime | None = None,
    ) -> datetime:
        total_hours = 0.0
        for line in self.service_lines:
            estimated_hours = service_hours.get(line.service_id)
            if estimated_hours is not None:
                total_hours += estimated_hours * line.quantity

        MAX_HOURS_ALLOWED = 4380

        if MAX_HOURS_ALLOWED < total_hours:
            raise ValidationError(
                "O tempo estimado de entrega excede o limite permitido (6 meses). Por favor, revise os serviços adicionados ao orçamento."
            )

        current_time = now or datetime.now(ZoneInfo("America/Sao_Paulo"))
        self.estimated_delivery = current_time + timedelta(
            hours=int(min(max(total_hours, 1), MAX_HOURS_ALLOWED))
        )
        return self.estimated_delivery

    def recalculate_total_price(self) -> float:
        self.total_price = sum(line.unit_price * line.quantity for line in self.service_lines) + sum(
            line.unit_price * line.quantity for line in self.product_lines
        )
        return self.total_price

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
