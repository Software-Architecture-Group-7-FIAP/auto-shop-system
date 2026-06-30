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
    create_signed_approval_token,
    validate_approval_token,
)
from src.infrastructure.database import (
    CustomerModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
    ServiceOrderServiceLineModel,
    VehicleModel,
)
from src.infrastructure.email.service import send_email
from src.infrastructure.pdf.generator import generate_budget_pdf


class SignedBudgetApprovalTokenService:
    def create_for_budget(self, budget_id: int) -> str:
        return create_signed_approval_token(budget_id)

    def validate(self, token: str) -> int:
        return validate_approval_token(token)


class SettingsBudgetApprovalUrlBuilder:
    def approve_url(self, token: str) -> str:
        return f"{settings.app_base_url}/api/v1/public/budgets/{token}/approve"

    def reject_url(self, token: str) -> str:
        return f"{settings.app_base_url}/api/v1/public/budgets/{token}/reject"


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

        service_order = ServiceOrderModel(
            budget_id=budget.id,
            customer_id=budget.customer_id,
            vehicle_id=budget.vehicle_id,
            status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
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
