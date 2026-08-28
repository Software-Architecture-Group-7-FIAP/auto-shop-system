from datetime import datetime, timedelta, timezone

import pytest

from src.domain.budget.entity import Budget, BudgetProductLine, BudgetServiceLine
from src.domain.enums import BudgetStatus
from src.domain.exceptions import ValidationError


def make_budget(**overrides: object) -> Budget:
    values: dict[str, object] = {
        "id": 1,
        "customer_id": 2,
        "vehicle_id": 3,
        "service_lines": [BudgetServiceLine(1, 1, 10, 1, 100.0)],
        "product_lines": [BudgetProductLine(2, 1, 20, 2, 5.0)],
    }
    values.update(overrides)
    return Budget(**values)


def test_sent_revision_is_immutable() -> None:
    budget = make_budget()
    budget.mark_sent("fingerprint", datetime.now(timezone.utc) + timedelta(hours=1))

    with pytest.raises(ValidationError, match="rascunho"):
        budget.update_service_line(1, 2)
    with pytest.raises(ValidationError, match="rascunho"):
        budget.add_product_line(21, 1, 5.0, False)


def test_approval_and_rejection_require_sent_revision() -> None:
    draft = make_budget()
    with pytest.raises(ValidationError, match="enviado"):
        draft.approve()
    with pytest.raises(ValidationError, match="enviado"):
        draft.reject()


def test_expired_approval_cannot_be_decided() -> None:
    budget = make_budget()
    budget.mark_sent("fingerprint", datetime.now(timezone.utc) - timedelta(seconds=1))

    with pytest.raises(ValidationError, match="expirado"):
        budget.approve()


def test_revision_is_cloned_as_new_draft_and_lines_are_detached() -> None:
    budget = make_budget(status=BudgetStatus.APPROVED)
    revision = budget.clone_as_revision()

    assert revision.id is None
    assert revision.status == BudgetStatus.DRAFT
    assert revision.revision_number == budget.revision_number + 1
    assert revision.supersedes_budget_id == budget.id
    assert revision.service_lines[0] is not budget.service_lines[0]
    assert revision.product_lines[0] is not budget.product_lines[0]


def test_terminal_revision_cannot_be_superseded() -> None:
    budget = make_budget(status=BudgetStatus.APPROVED)

    with pytest.raises(ValidationError, match="pendente"):
        budget.supersede()
