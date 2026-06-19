from sqlalchemy.orm import Session

from src.application.services.budget_service import BudgetService
from src.infrastructure.persistence.budget_repository import (
    SqlAlchemyBudgetProductLookup,
    SqlAlchemyBudgetRepository,
    SqlAlchemyBudgetServiceCatalogLookup,
    SqlAlchemyReservationLookup,
    SqlAlchemyVehicleOwnershipLookup,
)
from src.infrastructure.persistence.customer_repository import SqlAlchemyCustomerLookup
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_budget_service(db: Session) -> BudgetService:
    return BudgetService(
        budgets=SqlAlchemyBudgetRepository(db),
        customers=SqlAlchemyCustomerLookup(db),
        vehicles=SqlAlchemyVehicleOwnershipLookup(db),
        services=SqlAlchemyBudgetServiceCatalogLookup(db),
        products=SqlAlchemyBudgetProductLookup(db),
        reservations=SqlAlchemyReservationLookup(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
