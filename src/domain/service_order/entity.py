from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar

from src.domain.enums import Priority, ServiceOrderStatus
from src.domain.exceptions import ValidationError


@dataclass(frozen=True)
class ServiceOrderStatusTransition:
    """Append-only audit record for a service-order status transition."""

    from_status: ServiceOrderStatus
    to_status: ServiceOrderStatus
    transition_type: str
    reason: str | None = None
    actor_id: int | None = None
    request_id: str | None = None
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


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
    status_history: list[ServiceOrderStatusTransition] = field(default_factory=list)

    _ALLOWED_TRANSITIONS: ClassVar[dict[ServiceOrderStatus, frozenset[ServiceOrderStatus]]] = {
        ServiceOrderStatus.RECEBIDA: frozenset({ServiceOrderStatus.EM_DIAGNOSTICO}),
        ServiceOrderStatus.EM_DIAGNOSTICO: frozenset(
            {ServiceOrderStatus.AGUARDANDO_APROVACAO}
        ),
        ServiceOrderStatus.AGUARDANDO_APROVACAO: frozenset(
            {ServiceOrderStatus.AGUARDANDO_INICIO}
        ),
        ServiceOrderStatus.AGUARDANDO_INICIO: frozenset(
            {ServiceOrderStatus.EM_EXECUCAO}
        ),
        ServiceOrderStatus.EM_EXECUCAO: frozenset({ServiceOrderStatus.FINALIZADA}),
        ServiceOrderStatus.FINALIZADA: frozenset({ServiceOrderStatus.ENTREGUE}),
        ServiceOrderStatus.ENTREGUE: frozenset(),
    }

    _BREAK_GLASS_STATUSES: ClassVar[frozenset[ServiceOrderStatus]] = frozenset(
        {
            ServiceOrderStatus.RECEBIDA,
            ServiceOrderStatus.EM_DIAGNOSTICO,
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
        }
    )

    # An approved budget revision may only rewrite the scope of an OS that has
    # not started work yet. Owned here so persistence adapters state the rule
    # by asking the aggregate rather than re-implementing it.
    _REVISABLE_STATUSES: ClassVar[frozenset[ServiceOrderStatus]] = frozenset(
        {
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
            ServiceOrderStatus.AGUARDANDO_INICIO,
        }
    )

    @property
    def is_terminal(self) -> bool:
        return self.status == ServiceOrderStatus.ENTREGUE

    def transition_to(
        self,
        status: ServiceOrderStatus,
        *,
        transition_type: str = "workflow",
        reason: str | None = None,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Move the aggregate through one edge of the canonical workflow."""
        if status == self.status:
            raise ValidationError("OS já está neste status")
        if status not in self._ALLOWED_TRANSITIONS.get(self.status, frozenset()):
            raise ValidationError(
                f"Transição de {self.status.value} para {status.value} não permitida"
            )

        previous = self.status
        self.status = status
        self.status_history.append(
            ServiceOrderStatusTransition(
                from_status=previous,
                to_status=status,
                transition_type=transition_type,
                reason=reason,
                actor_id=actor_id,
                request_id=request_id,
            )
        )

    def assign_mechanic(
        self,
        mechanic_name: str,
        reason: str | None = None,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        cleaned_name = mechanic_name.strip()
        if not cleaned_name:
            raise ValidationError("Nome do mecânico é obrigatório")

        if self.mechanic_name is None:
            if self.status != ServiceOrderStatus.RECEBIDA:
                raise ValidationError(
                    "A primeira atribuição de mecânico só é permitida para OS recebida"
                )
            self.mechanic_name = cleaned_name
            self.transition_to(
                ServiceOrderStatus.EM_DIAGNOSTICO,
                transition_type="mechanic_assignment",
                actor_id=actor_id,
                request_id=request_id,
            )
            return

        if cleaned_name == self.mechanic_name:
            return
        if self.status in {
            ServiceOrderStatus.FINALIZADA,
            ServiceOrderStatus.ENTREGUE,
        }:
            raise ValidationError("Não é possível trocar o mecânico de uma OS encerrada")
        if not reason or not reason.strip():
            raise ValidationError("Motivo da troca de mecânico é obrigatório")
        self.mechanic_name = cleaned_name
        self.status_history.append(
            ServiceOrderStatusTransition(
                from_status=self.status,
                to_status=self.status,
                transition_type="mechanic_reassignment",
                reason=reason.strip(),
                actor_id=actor_id,
                request_id=request_id,
            )
        )

    def submit_for_approval(
        self,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        self.transition_to(
            ServiceOrderStatus.AGUARDANDO_APROVACAO,
            transition_type="budget_submitted",
            actor_id=actor_id,
            request_id=request_id,
        )

    def approve_current_budget(
        self,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        self.transition_to(
            ServiceOrderStatus.AGUARDANDO_INICIO,
            transition_type="budget_approved",
            actor_id=actor_id,
            request_id=request_id,
        )

    def ensure_can_apply_budget_revision(self) -> None:
        if self.status not in self._REVISABLE_STATUSES:
            raise ValidationError("A revisão não pode alterar a OS neste status")

    def apply_budget_revision(
        self,
        total_price: float,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Adopt an approved revision's scope, advancing the OS if needed."""
        self.ensure_can_apply_budget_revision()
        if self.status == ServiceOrderStatus.AGUARDANDO_APROVACAO:
            self.approve_current_budget(actor_id=actor_id, request_id=request_id)
        self.total_price = total_price

    def record_queue_entry(
        self,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log that the OS was placed on the execution queue.

        The queue is derived from the status, so this adds no transition — but
        it must still name who queued the OS, like every other audited action.
        """
        if self.status != ServiceOrderStatus.AGUARDANDO_INICIO:
            raise ValidationError("OS deve estar aguardando início para entrar na fila")
        self.status_history.append(
            ServiceOrderStatusTransition(
                from_status=self.status,
                to_status=self.status,
                transition_type="execution_queued",
                actor_id=actor_id,
                request_id=request_id,
            )
        )

    def return_to_diagnosis_after_rejection(
        self,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Allow the customer to reject a revision without a break-glass override."""
        if self.status != ServiceOrderStatus.AGUARDANDO_APROVACAO:
            raise ValidationError("A OS não está aguardando aprovação")
        previous = self.status
        self.status = ServiceOrderStatus.EM_DIAGNOSTICO
        self.status_history.append(
            ServiceOrderStatusTransition(
                from_status=previous,
                to_status=ServiceOrderStatus.EM_DIAGNOSTICO,
                transition_type="budget_rejected",
                actor_id=actor_id,
                request_id=request_id,
            )
        )

    def start_execution(
        self,
        started_at: datetime,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        if self.status != ServiceOrderStatus.AGUARDANDO_INICIO:
            raise ValidationError("OS não pode ser iniciada neste status")
        if not self.mechanic_name or not self.mechanic_name.strip():
            raise ValidationError("Mecânico deve ser atribuído antes de iniciar a OS")
        self.transition_to(
            ServiceOrderStatus.EM_EXECUCAO,
            transition_type="execution_started",
            actor_id=actor_id,
            request_id=request_id,
        )
        self.started_at = started_at

    def finish_execution(
        self,
        finished_at: datetime,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        self.transition_to(
            ServiceOrderStatus.FINALIZADA,
            transition_type="execution_finished",
            actor_id=actor_id,
            request_id=request_id,
        )
        self.finished_at = finished_at

    def set_priority(self, priority: Priority) -> None:
        self.priority = priority

    def override_status(
        self,
        status: ServiceOrderStatus,
        reason: str,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        if not reason.strip():
            raise ValidationError("Motivo da alteração de status é obrigatório")
        if self.status not in self._BREAK_GLASS_STATUSES or status not in self._BREAK_GLASS_STATUSES:
            raise ValidationError(
                "Override administrativo só pode corrigir os estados iniciais da OS"
            )
        if self.status == status:
            raise ValidationError("OS já está neste status")
        previous = self.status
        self.status = status
        self.status_history.append(
            ServiceOrderStatusTransition(
                from_status=previous,
                to_status=status,
                transition_type="break_glass_override",
                reason=reason.strip(),
                actor_id=actor_id,
                request_id=request_id,
            )
        )

    def mark_delivered(
        self,
        *,
        actor_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        if self.status != ServiceOrderStatus.FINALIZADA:
            raise ValidationError("OS deve estar finalizada para ser entregue")
        self.transition_to(
            ServiceOrderStatus.ENTREGUE,
            transition_type="delivered",
            actor_id=actor_id,
            request_id=request_id,
        )
