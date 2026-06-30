"""Repair missing budget product line service reference.

Revision ID: 007
Revises: 006
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("budget_product_lines")}
    if "service_id" not in columns:
        op.add_column(
            "budget_product_lines",
            sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id"), nullable=True),
        )

    indexes = {index["name"] for index in inspect(bind).get_indexes("budget_product_lines")}
    if "ix_budget_product_lines_service_id" not in indexes:
        op.create_index(
            "ix_budget_product_lines_service_id",
            "budget_product_lines",
            ["service_id"],
        )


def downgrade() -> None:
    pass
