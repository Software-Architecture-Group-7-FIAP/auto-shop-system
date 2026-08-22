from datetime import datetime, timedelta

import pytest

from src.domain.budget.entity import Budget
from src.domain.enums import BudgetStatus
from src.domain.exceptions import ValidationError

FUTURE = datetime(2030, 1, 1)
PAST = datetime(2020, 1, 1)


def _sent_budget(**overrides) -> Budget:
    defaults = dict(
        id=1,
        customer_id=2,
        vehicle_id=3,
        status=BudgetStatus.SENT,
        approval_token_hash="fingerprint",
        approval_expires_at=FUTURE,
    )
    defaults.update(overrides)
    return Budget(**defaults)


def test_budget_mark_sent_stores_fingerprint_and_status():
    budget = Budget(id=1, customer_id=2, vehicle_id=3)

    budget.mark_sent("fingerprint-123", FUTURE)

    assert budget.approval_token_hash == "fingerprint-123"
    assert budget.approval_expires_at == FUTURE
    assert budget.status == BudgetStatus.SENT


def test_budget_mark_sent_rejects_blank_fingerprint():
    budget = Budget(id=1, customer_id=2, vehicle_id=3)

    with pytest.raises(ValidationError, match="Fingerprint do token"):
        budget.mark_sent("   ", FUTURE)


def test_budget_mark_sent_reissues_link_for_an_expired_sent_budget():
    budget = _sent_budget(approval_expires_at=PAST)

    budget.mark_sent("fingerprint-2", FUTURE)

    assert budget.status == BudgetStatus.SENT
    assert budget.approval_token_hash == "fingerprint-2"
    assert budget.approval_expires_at == FUTURE
    # The reissued link works, so the revision is not stranded.
    budget.approve(datetime(2029, 1, 1))
    assert budget.status == BudgetStatus.APPROVED


def test_budget_mark_sent_refuses_to_reissue_after_a_decision():
    budget = _sent_budget(approval_used_at=datetime(2025, 1, 1))

    with pytest.raises(ValidationError, match="já teve uma decisão registrada"):
        budget.mark_sent("fingerprint-2", FUTURE)


def test_budget_approve_changes_status():
    budget = _sent_budget()

    budget.approve(datetime(2025, 1, 1))

    assert budget.status == BudgetStatus.APPROVED
    assert budget.approval_used_at == datetime(2025, 1, 1)


def test_budget_approve_rejects_already_approved_budget():
    budget = Budget(id=1, customer_id=2, vehicle_id=3, status=BudgetStatus.APPROVED)

    with pytest.raises(ValidationError, match="Orçamento já aprovado"):
        budget.approve()


def test_budget_approve_rejects_expired_token_on_the_customer_path():
    budget = _sent_budget(approval_expires_at=PAST)

    with pytest.raises(ValidationError, match="Token de aprovação expirado"):
        budget.approve(datetime(2025, 1, 1))


def test_budget_approve_ignores_token_expiry_for_authenticated_staff():
    budget = _sent_budget(approval_expires_at=PAST)

    budget.approve(datetime(2025, 1, 1), require_token=False)

    assert budget.status == BudgetStatus.APPROVED


def test_budget_approve_by_staff_still_refuses_a_consumed_token():
    budget = _sent_budget(approval_used_at=datetime(2024, 6, 1))

    with pytest.raises(ValidationError, match="já teve uma decisão registrada"):
        budget.approve(datetime(2025, 1, 1), require_token=False)


def test_budget_reject_changes_status():
    budget = _sent_budget()

    budget.reject(datetime(2025, 1, 1))

    assert budget.status == BudgetStatus.REJECTED


def test_budget_approval_token_is_single_use():
    budget = _sent_budget()

    budget.approve(datetime(2025, 1, 1))

    with pytest.raises(ValidationError):
        budget.reject(datetime(2025, 1, 1) + timedelta(minutes=1))
