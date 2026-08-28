"""index the budget revision chain

Revision ID: 012
Revises: 011
"""

from typing import Sequence, Union

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Revision lookups walk parent/child links instead of scanning the whole
    # budgets table; the child direction needs this index to stay cheap.
    op.create_index(
        "ix_budgets_supersedes_budget_id", "budgets", ["supersedes_budget_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_budgets_supersedes_budget_id", table_name="budgets")
