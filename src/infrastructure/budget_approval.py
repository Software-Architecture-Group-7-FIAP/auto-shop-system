from datetime import datetime
from urllib.parse import quote

from sqlalchemy.orm import Session

from src.application.ports.budget_approval import (
    BudgetApprovalCustomer,
    BudgetApprovalVehicle,
    CreatedServiceOrder,
)
from src.config import settings
from src.domain.budget.entity import Budget
from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import ValidationError
from src.infrastructure.auth.tokens import (
    approval_token_expires_at,
    approval_token_fingerprint,
    create_signed_approval_token,
    validate_approval_token,
)
from src.infrastructure.database import (
    BudgetModel,
    CustomerModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
    ServiceOrderServiceLineModel,
    VehicleModel,
)
from src.infrastructure.persistence.service_order_repository import SqlAlchemyServiceOrderRepository
from src.infrastructure.email.service import send_email
from src.infrastructure.pdf.generator import generate_budget_pdf


class SignedBudgetApprovalTokenService:
    def create_for_budget(self, budget_id: int) -> str:
        return create_signed_approval_token(budget_id)

    def validate(self, token: str) -> int:
        return validate_approval_token(token)

    def fingerprint(self, token: str) -> str:
        return approval_token_fingerprint(token)

    def expires_at(self, token: str) -> datetime:
        return approval_token_expires_at(token)


class SettingsBudgetApprovalUrlBuilder:
    def approve_url(self, token: str) -> str:
        return self._frontend_url(token, "approve")

    def reject_url(self, token: str) -> str:
        return self._frontend_url(token, "reject")

    @staticmethod
    def _frontend_url(token: str, action: str) -> str:
        # Keep the bearer token in the URL fragment. Fragments are not sent in
        # HTTP Referer headers or server access logs; the frontend must remove
        # it with history.replaceState after exchanging it for the API.
        return (
            f"{settings.frontend_public_url.rstrip('/')}/budget-approval"
            f"?action={quote(action)}#{quote(token)}"
        )


class ReportLabBudgetPdfGenerator:
    def generate_budget_pdf(
        self,
        budget_id: int,
        customer_name: str,
        vehicle_plate: str,
        service_lines: list[dict],
        product_lines: list[dict],
        total_price: float,
    ) -> bytes:
        return generate_budget_pdf(
            budget_id,
            customer_name,
            vehicle_plate,
            service_lines,
            product_lines,
            total_price,
        )


class SmtpEmailSender:
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        await send_email(to, subject, body, html)


class SqlAlchemyBudgetApprovalContactLookup:
    def __init__(self, db: Session):
        self.db = db

    def get_customer(self, customer_id: int) -> BudgetApprovalCustomer | None:
        model = self.db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        if not model:
            return None
        return BudgetApprovalCustomer(name=model.name, email=model.email)

    def get_vehicle(self, vehicle_id: int) -> BudgetApprovalVehicle | None:
        model = self.db.query(VehicleModel).filter(VehicleModel.id == vehicle_id).first()
        if not model:
            return None
        return BudgetApprovalVehicle(plate=model.plate)


class SqlAlchemyApprovedBudgetServiceOrderCreator:
    def __init__(self, db: Session):
        self.db = db

    def create_from_budget(self, budget: Budget) -> CreatedServiceOrder:
        if budget.id is None:
            raise ValidationError("Orçamento precisa estar persistido")

        # Revisions point back to the original commercial budget. Never create
        # a second OS when a related revision already has one.
        existing = self._find_order_for_budget(budget.id)
        if existing is not None:
            return CreatedServiceOrder(id=existing.id)

        root_budget_id = self._root_budget_id(budget.id)

        service_order = ServiceOrderModel(
            budget_id=root_budget_id,
            customer_id=budget.customer_id,
            vehicle_id=budget.vehicle_id,
            status=ServiceOrderStatus.RECEBIDA,
            total_price=budget.total_price,
        )
        self.db.add(service_order)
        self.db.flush()

        for line in budget.service_lines:
            self.db.add(
                ServiceOrderServiceLineModel(
                    service_order_id=service_order.id,
                    service_id=line.service_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                )
            )
        for line in budget.product_lines:
            self.db.add(
                ServiceOrderProductLineModel(
                    service_order_id=service_order.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                )
            )

        self.db.flush()
        self.db.refresh(service_order)
        return CreatedServiceOrder(id=service_order.id)

    def apply_approved_revision(self, budget: Budget, *, actor_id: int | None = None, request_id: str | None = None) -> CreatedServiceOrder:
        """Create the first OS or atomically apply a later budget snapshot."""
        if budget.id is None:
            raise ValidationError("Orçamento precisa estar persistido")
        service_order = self._find_order_for_budget(budget.id)
        if service_order is None:
            return self.create_from_budget(budget)

        repository = SqlAlchemyServiceOrderRepository(self.db)
        domain_order = repository.get_by_id(service_order.id)
        if domain_order is None:
            raise ValidationError("OS não encontrada")
        # The aggregate owns which statuses a revision may rewrite.
        domain_order.apply_budget_revision(
            budget.total_price, actor_id=actor_id, request_id=request_id
        )
        repository.save(domain_order)
        service_order.status = domain_order.status
        service_order.total_price = domain_order.total_price
        self.db.query(ServiceOrderServiceLineModel).filter(
            ServiceOrderServiceLineModel.service_order_id == service_order.id
        ).delete(synchronize_session=False)
        self.db.query(ServiceOrderProductLineModel).filter(
            ServiceOrderProductLineModel.service_order_id == service_order.id
        ).delete(synchronize_session=False)
        for line in budget.service_lines:
            self.db.add(ServiceOrderServiceLineModel(
                service_order_id=service_order.id,
                service_id=line.service_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
            ))
        for line in budget.product_lines:
            self.db.add(ServiceOrderProductLineModel(
                service_order_id=service_order.id,
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
            ))
        self.db.flush()
        return CreatedServiceOrder(id=service_order.id)

    def return_to_diagnosis(self, budget_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> None:
        service_order = self._find_order_for_budget(budget_id)
        if service_order is None:
            return
        repository = SqlAlchemyServiceOrderRepository(self.db)
        domain_order = repository.get_by_id(service_order.id)
        if domain_order is None:
            return
        domain_order.return_to_diagnosis_after_rejection(actor_id=actor_id, request_id=request_id)
        repository.save(domain_order)

    def submit_for_approval(self, budget_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> None:
        service_order = self._find_order_for_budget(budget_id)
        if service_order is None:
            return
        repository = SqlAlchemyServiceOrderRepository(self.db)
        domain_order = repository.get_by_id(service_order.id)
        if domain_order is None:
            return
        if domain_order.status == ServiceOrderStatus.EM_DIAGNOSTICO:
            domain_order.submit_for_approval(actor_id=actor_id, request_id=request_id)
        repository.save(domain_order)

    def get_by_budget_id(self, budget_id: int) -> CreatedServiceOrder | None:
        model = self._find_order_for_budget(budget_id)
        return CreatedServiceOrder(id=model.id) if model else None

    def _find_order_for_budget(self, budget_id: int) -> ServiceOrderModel | None:
        current_id = budget_id
        visited: set[int] = set()
        while current_id not in visited:
            visited.add(current_id)
            model = (
                self.db.query(ServiceOrderModel)
                .filter(ServiceOrderModel.budget_id == current_id)
                .with_for_update()
                .first()
            )
            if model:
                return model
            budget = (
                self.db.query(BudgetModel)
                .filter(BudgetModel.id == current_id)
                .with_for_update()
                .first()
            )
            if not budget or budget.supersedes_budget_id is None:
                return None
            current_id = budget.supersedes_budget_id
        return None

    def _root_budget_id(self, budget_id: int) -> int:
        current_id = budget_id
        visited: set[int] = set()
        while current_id not in visited:
            visited.add(current_id)
            budget = (
                self.db.query(BudgetModel)
                .filter(BudgetModel.id == current_id)
                .with_for_update()
                .first()
            )
            if budget is None or budget.supersedes_budget_id is None:
                return current_id
            current_id = budget.supersedes_budget_id
        return current_id
