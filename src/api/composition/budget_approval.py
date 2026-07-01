from sqlalchemy.orm import Session

from src.application.services.budget_approval_service import BudgetApprovalService
from src.infrastructure.budget_approval import (
    ReportLabBudgetPdfGenerator,
    SettingsBudgetApprovalUrlBuilder,
    SignedBudgetApprovalTokenService,
    SmtpEmailSender,
    SqlAlchemyApprovedBudgetServiceOrderCreator,
    SqlAlchemyBudgetApprovalContactLookup,
)
from src.infrastructure.persistence.budget_repository import SqlAlchemyBudgetRepository
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_budget_approval_service(db: Session) -> BudgetApprovalService:
    return BudgetApprovalService(
        budgets=SqlAlchemyBudgetRepository(db),
        contacts=SqlAlchemyBudgetApprovalContactLookup(db),
        tokens=SignedBudgetApprovalTokenService(),
        urls=SettingsBudgetApprovalUrlBuilder(),
        pdfs=ReportLabBudgetPdfGenerator(),
        emails=SmtpEmailSender(),
        service_orders=SqlAlchemyApprovedBudgetServiceOrderCreator(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
