"""add service_id to budget_product_lines

Revision ID: 004
Revises: 003
Create Date: 2026-06-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "budget_product_lines",
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id"), nullable=True),
    )
    op.create_index("ix_budget_product_lines_service_id", "budget_product_lines", ["service_id"])


def downgrade() -> None:
    op.drop_index("ix_budget_product_lines_service_id", table_name="budget_product_lines")
    op.drop_column("budget_product_lines", "service_id")
