from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar
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
    # A fingerprint is safe to carry in the domain model; the raw bearer
    # token is intentionally not represented here.
    approval_token_hash: str | None = None
    approval_expires_at: datetime | None = None
    approval_used_at: datetime | None = None
    revision_number: int = 1
    supersedes_budget_id: int | None = None
    created_at: datetime | None = None
    service_lines: list[BudgetServiceLine] = field(default_factory=list)
    product_lines: list[BudgetProductLine] = field(default_factory=list)

    _ALLOWED_TRANSITIONS: ClassVar[dict[BudgetStatus, frozenset[BudgetStatus]]] = {
        BudgetStatus.DRAFT: frozenset({BudgetStatus.SENT, BudgetStatus.SUPERSEDED}),
        BudgetStatus.SENT: frozenset(
            {BudgetStatus.APPROVED, BudgetStatus.REJECTED, BudgetStatus.SUPERSEDED}
        ),
        BudgetStatus.APPROVED: frozenset(),
        BudgetStatus.REJECTED: frozenset(),
        BudgetStatus.SUPERSEDED: frozenset(),
    }

    @classmethod
    def create(cls, customer_id: int, vehicle_id: int) -> "Budget":
        return cls(id=None, customer_id=customer_id, vehicle_id=vehicle_id)

    def transition_to(self, status: BudgetStatus) -> None:
        if status == self.status:
            raise ValidationError("Orçamento já está neste status")
        if status not in self._ALLOWED_TRANSITIONS.get(self.status, frozenset()):
            raise ValidationError(
                f"Transição de {self.status.value} para {status.value} não permitida"
            )
        self.status = status

    def add_service_line(self, service_id: int, quantity: int, base_price: int, resolved_requirements: list[dict]) -> BudgetServiceLine:
        self._ensure_editable()
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
        self._ensure_editable()
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
        self._ensure_editable()
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
        self._ensure_editable()
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
        self._ensure_editable()
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
        self._ensure_editable()
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
        self._ensure_editable()
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
        self._ensure_editable()
        self.total_price = sum(line.unit_price * line.quantity for line in self.service_lines) + sum(
            line.unit_price * line.quantity for line in self.product_lines
        )
        return self.total_price

    def mark_sent(self, token_hash: str, expires_at: datetime) -> None:
        """Send the revision, or reissue the approval link for a sent one.

        Reissuing matters because the customer link expires: without it an
        ignored e-mail would strand the revision forever, since an expired
        token blocks approve, reject and every further edit.
        """
        if not token_hash or not token_hash.strip():
            raise ValidationError("Fingerprint do token de aprovação é obrigatório")
        if self.status == BudgetStatus.SENT:
            if self.approval_used_at is not None:
                raise ValidationError("Orçamento já teve uma decisão registrada")
            self.approval_token_hash = token_hash
            self.approval_expires_at = expires_at
            return
        if self.status != BudgetStatus.DRAFT:
            raise ValidationError("Somente uma revisão em rascunho pode ser enviada")
        self.approval_token_hash = token_hash
        self.approval_expires_at = expires_at
        self.approval_used_at = None
        self.transition_to(BudgetStatus.SENT)

    def mark_approval_used(self, used_at: datetime) -> None:
        self.approval_used_at = used_at

    def approve(
        self,
        approved_at: datetime | None = None,
        *,
        require_token: bool = True,
    ) -> None:
        """Approve the revision.

        ``require_token`` is the customer path, where the decision rides on the
        public bearer token and must respect its expiry. An authenticated staff
        approval (customer confirmed by phone) passes ``False``: the e-mail
        link's TTL says nothing about whether an admin may approve.
        """
        if self.status == BudgetStatus.APPROVED:
            raise ValidationError("Orçamento já aprovado")
        if self.status != BudgetStatus.SENT:
            raise ValidationError("Somente um orçamento enviado pode ser aprovado")
        decision_time = approved_at or datetime.now(ZoneInfo("UTC"))
        self._ensure_decidable(decision_time, require_token)
        self.transition_to(BudgetStatus.APPROVED)
        self.approval_used_at = decision_time

    def reject(
        self,
        rejected_at: datetime | None = None,
        *,
        require_token: bool = True,
    ) -> None:
        if self.status == BudgetStatus.REJECTED:
            raise ValidationError("Orçamento já recusado")
        if self.status != BudgetStatus.SENT:
            raise ValidationError("Somente um orçamento enviado pode ser recusado")
        decision_time = rejected_at or datetime.now(ZoneInfo("UTC"))
        self._ensure_decidable(decision_time, require_token)
        self.transition_to(BudgetStatus.REJECTED)
        self.approval_used_at = decision_time

    def supersede(self) -> None:
        if self.status not in (BudgetStatus.DRAFT, BudgetStatus.SENT):
            raise ValidationError("Somente uma revisão pendente pode ser substituída")
        self.transition_to(BudgetStatus.SUPERSEDED)
        self.approval_token_hash = None
        self.approval_expires_at = None

    def clone_as_revision(self) -> "Budget":
        """Return an editable snapshot for a new diagnostic revision."""
        if self.status != BudgetStatus.APPROVED:
            raise ValidationError("A nova revisão deve ser clonada da revisão aprovada")

        revision = Budget(
            id=None,
            customer_id=self.customer_id,
            vehicle_id=self.vehicle_id,
            status=BudgetStatus.DRAFT,
            total_price=self.total_price,
            estimated_delivery=self.estimated_delivery,
            revision_number=self.revision_number + 1,
            supersedes_budget_id=self.id,
        )
        revision.service_lines = [
            BudgetServiceLine(
                id=None,
                budget_id=0,
                service_id=line.service_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
            for line in self.service_lines
        ]
        revision.product_lines = [
            BudgetProductLine(
                id=None,
                budget_id=0,
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
                from_service=line.from_service,
                service_id=line.service_id,
            )
            for line in self.product_lines
        ]
        return revision

    def _ensure_editable(self) -> None:
        if self.status != BudgetStatus.DRAFT:
            raise ValidationError("Somente revisões em rascunho podem ser editadas")

    def _ensure_decidable(self, now: datetime, require_token: bool) -> None:
        if require_token:
            self._ensure_approval_active(now)
        elif self.approval_used_at is not None:
            raise ValidationError("Orçamento já teve uma decisão registrada")

    def _ensure_approval_active(self, now: datetime) -> None:
        if self.approval_used_at is not None:
            raise ValidationError("Token de aprovação já foi utilizado")
        if self.approval_expires_at is None:
            raise ValidationError("Token de aprovação sem expiração")
        expires_at = self.approval_expires_at
        if expires_at.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        if now >= expires_at:
            raise ValidationError("Token de aprovação expirado")

    def _required_id(self) -> int:
        if self.id is None:
            raise ValidationError("Orçamento precisa estar persistido")
        return self.id
