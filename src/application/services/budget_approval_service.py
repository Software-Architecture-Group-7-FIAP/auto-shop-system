from dataclasses import dataclass
from datetime import datetime, timezone

from src.application.ports.budget_approval import (
    ApprovedBudgetServiceOrderCreator,
    BudgetApprovalContactLookup,
    BudgetApprovalTokenService,
    BudgetApprovalUrlBuilder,
    BudgetPdfGenerator,
    CreatedServiceOrder,
    EmailSender,
)
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.budget.entity import Budget
from src.domain.budget.repository import BudgetRepository
from src.domain.enums import BudgetStatus
from src.domain.exceptions import NotFoundError, ValidationError

INVALID_APPROVAL_TOKEN_MESSAGE = "Orçamento inválido ou expirado"


@dataclass(frozen=True)
class BudgetDecisionResult:
    status: BudgetStatus
    service_order: CreatedServiceOrder | None = None
    already_processed: bool = False


class BudgetApprovalService:
    def __init__(
        self,
        budgets: BudgetRepository,
        contacts: BudgetApprovalContactLookup,
        tokens: BudgetApprovalTokenService,
        urls: BudgetApprovalUrlBuilder,
        pdfs: BudgetPdfGenerator,
        emails: EmailSender,
        service_orders: ApprovedBudgetServiceOrderCreator,
        uow: UnitOfWork,
    ):
        self.budgets = budgets
        self.contacts = contacts
        self.tokens = tokens
        self.urls = urls
        self.pdfs = pdfs
        self.emails = emails
        self.service_orders = service_orders
        self.uow = uow

    async def send_budget_email(self, budget_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> Budget:
        budget = self._get_by_id(budget_id)
        if budget.id is None:
            raise NotFoundError("Orçamento não encontrado")

        raw_token = self.tokens.create_for_budget(budget.id)
        budget.mark_sent(self.tokens.fingerprint(raw_token), self.tokens.expires_at(raw_token))
        updated_budget = self.budgets.save(budget)
        submit_for_approval = getattr(self.service_orders, "submit_for_approval", None)
        if submit_for_approval and updated_budget.id is not None:
            submit_for_approval(updated_budget.id, actor_id=actor_id, request_id=request_id)

        customer = self.contacts.get_customer(updated_budget.customer_id)
        vehicle = self.contacts.get_vehicle(updated_budget.vehicle_id)
        customer_name = customer.name if customer else ""
        customer_email = customer.email if customer else ""
        vehicle_plate = vehicle.plate if vehicle else ""
        service_lines = [
            {"name": f"Serviço #{line.service_id}", "quantity": line.quantity,
             "total": line.unit_price * line.quantity}
            for line in updated_budget.service_lines
        ]
        product_lines = [
            {"name": f"Produto #{line.product_id}", "quantity": line.quantity,
             "total": line.unit_price * line.quantity}
            for line in updated_budget.product_lines
        ]
        self.pdfs.generate_budget_pdf(
            updated_budget.id, customer_name, vehicle_plate, service_lines,
            product_lines, updated_budget.total_price,
        )

        approve_url = self.urls.approve_url(raw_token)
        reject_url = self.urls.reject_url(raw_token)
        html = f"""
        <p>Olá {customer_name},</p>
        <p>Segue seu orçamento #{updated_budget.id} no valor de R$ {updated_budget.total_price:.2f}.</p>
        <p><a href="{approve_url}">Aprovar orçamento</a> | <a href="{reject_url}">Recusar orçamento</a></p>
        """
        await self.emails.send_email(
            customer_email,
            f"Orçamento #{updated_budget.id}",
            f"Orçamento #{updated_budget.id} - Total: R$ {updated_budget.total_price:.2f}. Aprovar: {approve_url}",
            html,
        )
        self.uow.commit()
        return updated_budget

    def approve_budget(self, token: str) -> CreatedServiceOrder:
        result = self.decide_budget(token, "approve")
        if result.service_order is None:
            raise ValidationError("Orçamento aprovado sem OS associada")
        return result.service_order

    def approve_budget_by_id(self, budget_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> CreatedServiceOrder:
        get_for_update = getattr(self.budgets, "get_by_id_for_update", None)
        budget = get_for_update(budget_id) if get_for_update else self._get_by_id(budget_id)
        if budget is None:
            raise NotFoundError("Orçamento não encontrado")
        self._validate_can_approve(budget)
        # Staff approval is authenticated; it must not inherit the expiry of
        # the customer's e-mail link.
        budget.approve(require_token=False)
        updated_budget = self.budgets.save(budget)
        apply_revision = getattr(self.service_orders, "apply_approved_revision", None)
        service_order = (
            apply_revision(updated_budget, actor_id=actor_id, request_id=request_id)
            if apply_revision
            else self.service_orders.create_from_budget(updated_budget)
        )
        self.uow.commit()
        return service_order

    def decide_budget(self, token: str, decision: str, *, actor_id: int | None = None, request_id: str | None = None) -> BudgetDecisionResult:
        if decision not in {"approve", "reject"}:
            raise ValidationError("Decisão de orçamento inválida")
        budget = self._get_budget_by_valid_token(token)
        if budget.approval_used_at is not None:
            expected = BudgetStatus.APPROVED if decision == "approve" else BudgetStatus.REJECTED
            if budget.status != expected:
                raise ValidationError("Orçamento já foi processado com outra decisão")
            get_order = getattr(self.service_orders, "get_by_budget_id", None)
            order = (
                get_order(budget.id)
                if decision == "approve" and budget.id is not None and get_order
                else None
            )
            return BudgetDecisionResult(budget.status, order, True)

        if decision == "approve":
            self._validate_can_approve(budget)
            budget.approve()
        else:
            if budget.status != BudgetStatus.SENT:
                raise ValidationError("Orçamento não está aguardando decisão")
            budget.reject()
        budget.mark_approval_used(datetime.now(timezone.utc).replace(tzinfo=None))
        updated_budget = self.budgets.save(budget)
        if decision == "approve":
            apply_revision = getattr(self.service_orders, "apply_approved_revision", None)
            order = (
                apply_revision(updated_budget, actor_id=actor_id, request_id=request_id)
                if apply_revision
                else self.service_orders.create_from_budget(updated_budget)
            )
        else:
            return_to_diagnosis = getattr(self.service_orders, "return_to_diagnosis", None)
            if return_to_diagnosis and updated_budget.id is not None:
                return_to_diagnosis(updated_budget.id, actor_id=actor_id, request_id=request_id)
            order = None
        self.uow.commit()
        return BudgetDecisionResult(updated_budget.status, order)

    def _validate_can_approve(self, budget: Budget) -> None:
        if budget.status == BudgetStatus.REJECTED:
            raise ValidationError("Orçamento recusado não pode ser aprovado")
        if not budget.service_lines and not budget.product_lines:
            raise ValidationError("Orçamento deve ter linhas de serviço ou produto para ser aprovado")

    def reject_budget(self, token: str) -> Budget:
        self.decide_budget(token, "reject")
        try:
            budget_id = self.tokens.validate(token)
        except ValueError:
            # A consumed token may have expired between the first decision
            # and this compatibility helper's return-value lookup.
            budget = self.budgets.get_by_approval_token_fingerprint(
                self.tokens.fingerprint(token)
            )
            if budget is not None:
                return budget
            raise NotFoundError(INVALID_APPROVAL_TOKEN_MESSAGE)
        return self._get_by_id(budget_id)

    def _get_budget_by_valid_token(self, token: str) -> Budget:
        fingerprint = self.tokens.fingerprint(token)
        try:
            budget_id = self.tokens.validate(token)
        except ValueError as exc:
            consumed = self.budgets.get_by_approval_token_fingerprint(fingerprint)
            if consumed and consumed.approval_used_at is not None:
                return consumed
            raise NotFoundError(INVALID_APPROVAL_TOKEN_MESSAGE) from exc
        budget = self.budgets.get_by_approval_token_fingerprint(fingerprint)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if not budget or budget.id != budget_id:
            raise NotFoundError(INVALID_APPROVAL_TOKEN_MESSAGE)
        if budget.approval_used_at is not None:
            return budget
        if budget.approval_expires_at is None or budget.approval_expires_at <= now:
            raise NotFoundError(INVALID_APPROVAL_TOKEN_MESSAGE)
        return budget

    def _budget_id_from_token(self, token: str) -> int:
        try:
            return self.tokens.validate(token)
        except ValueError as exc:
            raise NotFoundError(INVALID_APPROVAL_TOKEN_MESSAGE) from exc

    def _get_by_id(self, budget_id: int) -> Budget:
        budget = self.budgets.get_by_id(budget_id)
        if not budget:
            raise NotFoundError("Orçamento não encontrado")
        return budget
