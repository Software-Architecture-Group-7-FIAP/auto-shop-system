from sqlalchemy.orm import Session

from src.config import settings
from src.domain.enums import BudgetStatus, ServiceOrderStatus
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.auth.tokens import create_signed_approval_token
from src.infrastructure.database import (
    BudgetModel,
    CustomerModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
    ServiceOrderServiceLineModel,
    VehicleModel,
)
from src.infrastructure.email.service import send_email
from src.infrastructure.pdf.generator import generate_budget_pdf, generate_service_order_pdf


class BudgetApprovalService:
    def __init__(self, db: Session):
        self.db = db

    async def send_budget_email(self, budget_id: int) -> BudgetModel:
        budget = self.db.query(BudgetModel).filter(BudgetModel.id == budget_id).first()
        if not budget:
            raise NotFoundError("Orçamento não encontrado")
        customer = self.db.query(CustomerModel).filter(CustomerModel.id == budget.customer_id).first()
        vehicle = self.db.query(VehicleModel).filter(VehicleModel.id == budget.vehicle_id).first()

        token = create_signed_approval_token(budget.id)
        budget.approval_token = token
        budget.status = BudgetStatus.SENT

        service_lines = []
        for line in budget.service_lines:
            service = line.service_id
            service_lines.append(
                {
                    "name": f"Serviço #{service}",
                    "quantity": line.quantity,
                    "total": line.unit_price * line.quantity,
                }
            )
        product_lines = []
        for line in budget.product_lines:
            product_lines.append(
                {
                    "name": f"Produto #{line.product_id}",
                    "quantity": line.quantity,
                    "total": line.unit_price * line.quantity,
                }
            )

        pdf_bytes = generate_budget_pdf(
            budget.id,
            customer.name if customer else "",
            vehicle.plate if vehicle else "",
            service_lines,
            product_lines,
            budget.total_price,
        )

        approve_url = f"{settings.app_base_url}/api/v1/public/budgets/{token}/approve"
        reject_url = f"{settings.app_base_url}/api/v1/public/budgets/{token}/reject"
        html = f"""
        <p>Olá {customer.name},</p>
        <p>Segue seu orçamento #{budget.id} no valor de R$ {budget.total_price:.2f}.</p>
        <p><a href="{approve_url}">Aprovar orçamento</a> | <a href="{reject_url}">Recusar orçamento</a></p>
        """
        await send_email(
            customer.email,
            f"Orçamento #{budget.id}",
            f"Orçamento #{budget.id} - Total: R$ {budget.total_price:.2f}. Aprovar: {approve_url}",
            html,
        )
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def approve_budget(self, token: str) -> ServiceOrderModel:
        budget = self.db.query(BudgetModel).filter(BudgetModel.approval_token == token).first()
        if not budget:
            raise NotFoundError("Orçamento não encontrado")
        if budget.status == BudgetStatus.APPROVED:
            raise ValidationError("Orçamento já aprovado")
        budget.status = BudgetStatus.APPROVED
        return self._create_service_order_from_budget(budget)

    def reject_budget(self, token: str) -> BudgetModel:
        budget = self.db.query(BudgetModel).filter(BudgetModel.approval_token == token).first()
        if not budget:
            raise NotFoundError("Orçamento não encontrado")
        budget.status = BudgetStatus.REJECTED
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def _create_service_order_from_budget(self, budget: BudgetModel) -> ServiceOrderModel:
        os = ServiceOrderModel(
            budget_id=budget.id,
            customer_id=budget.customer_id,
            vehicle_id=budget.vehicle_id,
            status=ServiceOrderStatus.AGUARDANDO_APROVACAO,
            total_price=budget.total_price,
        )
        self.db.add(os)
        self.db.flush()

        for line in budget.service_lines:
            self.db.add(
                ServiceOrderServiceLineModel(
                    service_order_id=os.id,
                    service_id=line.service_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                )
            )
        for line in budget.product_lines:
            self.db.add(
                ServiceOrderProductLineModel(
                    service_order_id=os.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                )
            )
        self.db.commit()
        self.db.refresh(os)
        return os


class ServiceOrderEmailService:
    def __init__(self, db: Session):
        self.db = db

    async def send_os_email(self, service_order_id: int) -> None:
        os = self.db.query(ServiceOrderModel).filter(ServiceOrderModel.id == service_order_id).first()
        if not os:
            raise NotFoundError("OS não encontrada")
        customer = self.db.query(CustomerModel).filter(CustomerModel.id == os.customer_id).first()
        vehicle = self.db.query(VehicleModel).filter(VehicleModel.id == os.vehicle_id).first()

        pdf_bytes = generate_service_order_pdf(
            os.id,
            customer.name if customer else "",
            vehicle.plate if vehicle else "",
            os.status.value,
            os.mechanic_name,
            os.total_price,
        )
        await send_email(
            customer.email,
            f"Ordem de Serviço #{os.id}",
            f"Sua OS #{os.id} está com status: {os.status.value}",
        )
