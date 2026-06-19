from dataclasses import dataclass
from typing import Protocol

from src.domain.budget.entity import Budget


@dataclass(frozen=True)
class BudgetApprovalCustomer:
    name: str
    email: str


@dataclass(frozen=True)
class BudgetApprovalVehicle:
    plate: str


@dataclass(frozen=True)
class CreatedServiceOrder:
    id: int


class BudgetApprovalContactLookup(Protocol):
    def get_customer(self, customer_id: int) -> BudgetApprovalCustomer | None:
        ...

    def get_vehicle(self, vehicle_id: int) -> BudgetApprovalVehicle | None:
        ...


class BudgetApprovalTokenGenerator(Protocol):
    def create_for_budget(self, budget_id: int) -> str:
        ...


class BudgetApprovalUrlBuilder(Protocol):
    def approve_url(self, token: str) -> str:
        ...

    def reject_url(self, token: str) -> str:
        ...


class BudgetPdfGenerator(Protocol):
    def generate_budget_pdf(
        self,
        budget_id: int,
        customer_name: str,
        vehicle_plate: str,
        service_lines: list[dict],
        product_lines: list[dict],
        total_price: float,
    ) -> bytes:
        ...


class EmailSender(Protocol):
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        ...


class ApprovedBudgetServiceOrderCreator(Protocol):
    def create_from_budget(self, budget: Budget) -> CreatedServiceOrder:
        ...
