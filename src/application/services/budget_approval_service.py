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

    async def send_budget_email(self, budget_id: int) -> Budget:
        budget = self._get_by_id(budget_id)
        if budget.id is None:
            raise NotFoundError("Orçamento não encontrado")

        token = self.tokens.create_for_budget(budget.id)
        budget.mark_sent(token)
        updated_budget = self.budgets.save(budget)

        customer = self.contacts.get_customer(updated_budget.customer_id)
        vehicle = self.contacts.get_vehicle(updated_budget.vehicle_id)
        customer_name = customer.name if customer else ""
        customer_email = customer.email if customer else ""
        vehicle_plate = vehicle.plate if vehicle else ""

        service_lines = []
        for line in updated_budget.service_lines:
            service_lines.append(
                {
                    "name": f"Serviço #{line.service_id}",
                    "quantity": line.quantity,
                    "total": line.unit_price * line.quantity,
                }
            )
        product_lines = []
        for line in updated_budget.product_lines:
            product_lines.append(
                {
                    "name": f"Produto #{line.product_id}",
                    "quantity": line.quantity,
                    "total": line.unit_price * line.quantity,
                }
            )

        self.pdfs.generate_budget_pdf(
            updated_budget.id,
            customer_name,
            vehicle_plate,
            service_lines,
            product_lines,
            updated_budget.total_price,
        )

        approve_url = self.urls.approve_url(token)
        reject_url = self.urls.reject_url(token)
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
        budget = self._get_budget_by_valid_token(token)
        self._validate_can_approve(budget)
        return self._approve_and_create_service_order(budget)

    def approve_budget_by_id(self, budget_id: int) -> CreatedServiceOrder:
        budget = self._get_by_id(budget_id)
        self._validate_can_approve(budget)
        return self._approve_and_create_service_order(budget)

    def _validate_can_approve(self, budget: Budget) -> None:
        if budget.status == BudgetStatus.REJECTED:
            raise ValidationError("Orçamento recusado não pode ser aprovado")
        if not budget.service_lines and not budget.product_lines:
            raise ValidationError(
                "Orçamento deve ter linhas de serviço ou produto para ser aprovado"
            )

    def _approve_and_create_service_order(self, budget: Budget) -> CreatedServiceOrder:
        budget.approve()
        updated_budget = self.budgets.save(budget)
        service_order = self.service_orders.create_from_budget(updated_budget)
        self.uow.commit()
        return service_order

    def reject_budget(self, token: str) -> Budget:
        budget = self._get_budget_by_valid_token(token)

        budget.reject()
        updated_budget = self.budgets.save(budget)
        self.uow.commit()
        return updated_budget

    def _get_budget_by_valid_token(self, token: str) -> Budget:
        try:
            budget_id = self.tokens.validate(token)
        except ValueError as exc:
            raise NotFoundError(INVALID_APPROVAL_TOKEN_MESSAGE) from exc

        budget = self.budgets.get_by_id(budget_id)
        if not budget or budget.approval_token != token:
            raise NotFoundError(INVALID_APPROVAL_TOKEN_MESSAGE)
        return budget

    def _get_by_id(self, budget_id: int) -> Budget:
        budget = self.budgets.get_by_id(budget_id)
        if not budget:
            raise NotFoundError("Orçamento não encontrado")
        return budget
