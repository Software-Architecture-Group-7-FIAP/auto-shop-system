import pytest

from src.domain.budget.entity import Budget
from src.domain.enums import BudgetStatus
from src.domain.exceptions import ValidationError


def test_budget_mark_sent_stores_token_and_status():
    budget = Budget(id=1, customer_id=2, vehicle_id=3)

    budget.mark_sent("token-123")

    assert budget.approval_token == "token-123"
    assert budget.status == BudgetStatus.SENT


def test_budget_approve_changes_status():
    budget = Budget(id=1, customer_id=2, vehicle_id=3, status=BudgetStatus.SENT)

    budget.approve()

    assert budget.status == BudgetStatus.APPROVED


def test_budget_approve_rejects_already_approved_budget():
    budget = Budget(id=1, customer_id=2, vehicle_id=3, status=BudgetStatus.APPROVED)

    with pytest.raises(ValidationError, match="Orçamento já aprovado"):
        budget.approve()


def test_budget_reject_changes_status():
    budget = Budget(id=1, customer_id=2, vehicle_id=3, status=BudgetStatus.SENT)

    budget.reject()

    assert budget.status == BudgetStatus.REJECTED
