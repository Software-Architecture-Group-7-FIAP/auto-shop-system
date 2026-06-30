"""Ensure one product line per service product.

Revision ID: 006
Revises: 005
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM service_product_lines
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM service_product_lines
            GROUP BY service_id, product_id
        )
        """
    )
    with op.batch_alter_table("service_product_lines") as batch_op:
        batch_op.create_unique_constraint(
            "uq_service_product_line_product",
            ["service_id", "product_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("service_product_lines") as batch_op:
        batch_op.drop_constraint(
            "uq_service_product_line_product",
            type_="unique",
        )
