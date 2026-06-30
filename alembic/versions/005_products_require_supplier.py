"""Require supplier for products.

Revision ID: 005
Revises: 004a
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "005"
down_revision: Union[str, None] = "004a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO suppliers (name, document, email, phone, created_at)
        SELECT
            'Fornecedor não informado',
            '00000000000191',
            'fornecedor-nao-informado@oficina.local',
            NULL,
            CURRENT_TIMESTAMP
        WHERE EXISTS (SELECT 1 FROM products WHERE supplier_id IS NULL)
          AND NOT EXISTS (SELECT 1 FROM suppliers WHERE document = '00000000000191')
        """
    )
    op.execute(
        """
        UPDATE products
        SET supplier_id = (
            SELECT id
            FROM suppliers
            WHERE document = '00000000000191'
            LIMIT 1
        )
        WHERE supplier_id IS NULL
        """
    )
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column(
            "supplier_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column(
            "supplier_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
