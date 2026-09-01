from dataclasses import dataclass
from datetime import datetime
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


class BudgetApprovalTokenService(Protocol):
    def create_for_budget(self, budget_id: int) -> str:
        ...

    def validate(self, token: str) -> int:
        ...

    def fingerprint(self, token: str) -> str:
        ...

    def expires_at(self, token: str) -> datetime:
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


class ServiceOrderReservationReconciler(Protocol):
    def reconcile_for_service_order(self, service_order_id: int) -> None:
        ...

    def release_for_service_order(self, service_order_id: int) -> None:
        ...


class ApprovedBudgetServiceOrderCreator(Protocol):
    def create_from_budget(self, budget: Budget) -> CreatedServiceOrder:
        ...

    def get_by_budget_id(self, budget_id: int) -> CreatedServiceOrder | None:
        ...

    def apply_approved_revision(self, budget: Budget, *, actor_id: int | None = None, request_id: str | None = None) -> CreatedServiceOrder:
        """Atomically update the existing OS snapshot for a new revision."""
        ...

    def return_to_diagnosis(self, budget_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> None:
        ...

    def submit_for_approval(self, budget_id: int, *, actor_id: int | None = None, request_id: str | None = None) -> None:
        ...
