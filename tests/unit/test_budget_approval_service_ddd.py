from dataclasses import replace

import pytest

from src.application.ports.budget_approval import (
    BudgetApprovalCustomer,
    BudgetApprovalVehicle,
    CreatedServiceOrder,
)
from src.application.services.budget_approval_service import BudgetApprovalService
from src.domain.budget.entity import Budget, BudgetProductLine, BudgetServiceLine
from src.domain.enums import BudgetStatus
from src.domain.exceptions import NotFoundError, ValidationError


class InMemoryBudgetRepository:
    def __init__(self, budgets: list[Budget] | None = None):
        self.budgets = {budget.id: budget for budget in budgets or [] if budget.id is not None}

    def add(self, budget: Budget) -> Budget:
        created = replace(budget, id=len(self.budgets) + 1)
        self.budgets[created.id] = created
        return created

    def get_by_id(self, budget_id: int) -> Budget | None:
        return self.budgets.get(budget_id)

    def get_by_approval_token(self, token: str) -> Budget | None:
        for budget in self.budgets.values():
            if budget.approval_token == token:
                return budget
        return None

    def list_all(self) -> list[Budget]:
        return list(self.budgets.values())

    def add_service_line(self, line: BudgetServiceLine) -> BudgetServiceLine:
        return line

    def add_product_line(self, line: BudgetProductLine) -> BudgetProductLine:
        return line

    def save(self, budget: Budget) -> Budget:
        assert budget.id is not None
        self.budgets[budget.id] = budget
        return budget


class FakeContactLookup:
    def get_customer(self, customer_id: int) -> BudgetApprovalCustomer | None:
        return BudgetApprovalCustomer(name="Ana", email="ana@test.com")

    def get_vehicle(self, vehicle_id: int) -> BudgetApprovalVehicle | None:
        return BudgetApprovalVehicle(plate="ABC1234")


class FakeTokenGenerator:
    def create_for_budget(self, budget_id: int) -> str:
        return f"token-{budget_id}"


class FakeUrlBuilder:
    def approve_url(self, token: str) -> str:
        return f"https://app.test/api/v1/public/budgets/{token}/approve"

    def reject_url(self, token: str) -> str:
        return f"https://app.test/api/v1/public/budgets/{token}/reject"


class FakePdfGenerator:
    def __init__(self):
        self.calls = []

    def generate_budget_pdf(
        self,
        budget_id: int,
        customer_name: str,
        vehicle_plate: str,
        service_lines: list[dict],
        product_lines: list[dict],
        total_price: float,
    ) -> bytes:
        self.calls.append(
            {
                "budget_id": budget_id,
                "customer_name": customer_name,
                "vehicle_plate": vehicle_plate,
                "service_lines": service_lines,
                "product_lines": product_lines,
                "total_price": total_price,
            }
        )
        return b"pdf"


class FakeEmailSender:
    def __init__(self):
        self.messages = []

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        self.messages.append(
            {"to": to, "subject": subject, "body": body, "html": html}
        )


class FakeServiceOrderCreator:
    def __init__(self):
        self.created_from: list[Budget] = []

    def create_from_budget(self, budget: Budget) -> CreatedServiceOrder:
        self.created_from.append(budget)
        return CreatedServiceOrder(id=99)


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def make_budget() -> Budget:
    return Budget(
        id=1,
        customer_id=2,
        vehicle_id=3,
        total_price=125.0,
        service_lines=[
            BudgetServiceLine(
                id=10,
                budget_id=1,
                service_id=20,
                quantity=1,
                unit_price=100.0,
            )
        ],
        product_lines=[
            BudgetProductLine(
                id=11,
                budget_id=1,
                product_id=30,
                quantity=5,
                unit_price=5.0,
            )
        ],
    )


def make_service(
    repository: InMemoryBudgetRepository | None = None,
    pdfs: FakePdfGenerator | None = None,
    emails: FakeEmailSender | None = None,
    service_orders: FakeServiceOrderCreator | None = None,
    uow: FakeUnitOfWork | None = None,
) -> BudgetApprovalService:
    return BudgetApprovalService(
        budgets=repository or InMemoryBudgetRepository([make_budget()]),
        contacts=FakeContactLookup(),
        tokens=FakeTokenGenerator(),
        urls=FakeUrlBuilder(),
        pdfs=pdfs or FakePdfGenerator(),
        emails=emails or FakeEmailSender(),
        service_orders=service_orders or FakeServiceOrderCreator(),
        uow=uow or FakeUnitOfWork(),
    )


@pytest.mark.asyncio
async def test_send_budget_email_marks_budget_sent_and_sends_email():
    repository = InMemoryBudgetRepository([make_budget()])
    pdfs = FakePdfGenerator()
    emails = FakeEmailSender()
    uow = FakeUnitOfWork()
    service = make_service(repository=repository, pdfs=pdfs, emails=emails, uow=uow)

    budget = await service.send_budget_email(1)

    assert budget.status == BudgetStatus.SENT
    assert budget.approval_token == "token-1"
    assert repository.get_by_id(1).status == BudgetStatus.SENT
    assert pdfs.calls[0]["service_lines"] == [
        {"name": "Serviço #20", "quantity": 1, "total": 100.0}
    ]
    assert pdfs.calls[0]["product_lines"] == [
        {"name": "Produto #30", "quantity": 5, "total": 25.0}
    ]
    assert emails.messages[0]["to"] == "ana@test.com"
    assert (
        "Aprovar: https://app.test/api/v1/public/budgets/token-1/approve"
        in emails.messages[0]["body"]
    )
    assert uow.commits == 1


def test_approve_budget_marks_budget_approved_and_creates_service_order():
    budget = replace(make_budget(), status=BudgetStatus.SENT, approval_token="token-1")
    repository = InMemoryBudgetRepository([budget])
    service_orders = FakeServiceOrderCreator()
    uow = FakeUnitOfWork()
    service = make_service(
        repository=repository,
        service_orders=service_orders,
        uow=uow,
    )

    service_order = service.approve_budget("token-1")

    assert service_order.id == 99
    assert repository.get_by_id(1).status == BudgetStatus.APPROVED
    assert service_orders.created_from[0].status == BudgetStatus.APPROVED
    assert uow.commits == 1


def test_approve_budget_rejects_missing_token():
    service = make_service(repository=InMemoryBudgetRepository([make_budget()]))

    with pytest.raises(NotFoundError, match="Orçamento não encontrado"):
        service.approve_budget("missing")


def test_approve_budget_rejects_already_approved_budget_without_commit():
    budget = replace(make_budget(), status=BudgetStatus.APPROVED, approval_token="token-1")
    repository = InMemoryBudgetRepository([budget])
    service_orders = FakeServiceOrderCreator()
    uow = FakeUnitOfWork()
    service = make_service(
        repository=repository,
        service_orders=service_orders,
        uow=uow,
    )

    with pytest.raises(ValidationError, match="Orçamento já aprovado"):
        service.approve_budget("token-1")

    assert service_orders.created_from == []
    assert uow.commits == 0


def test_reject_budget_marks_budget_rejected():
    budget = replace(make_budget(), status=BudgetStatus.SENT, approval_token="token-1")
    repository = InMemoryBudgetRepository([budget])
    uow = FakeUnitOfWork()
    service = make_service(repository=repository, uow=uow)

    rejected = service.reject_budget("token-1")

    assert rejected.status == BudgetStatus.REJECTED
    assert repository.get_by_id(1).status == BudgetStatus.REJECTED
    assert uow.commits == 1
