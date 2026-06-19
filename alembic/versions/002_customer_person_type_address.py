"""customer person_type and address

Revision ID: 002
Revises: 001
Create Date: 2026-06-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("person_type", sa.String(2), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("address", sa.String(500), nullable=True),
    )

    op.execute(
        """
        UPDATE customers
        SET person_type = CASE
            WHEN LENGTH(document) = 11 THEN 'PF'
            WHEN LENGTH(document) = 14 THEN 'PJ'
            ELSE 'PF'
        END,
        address = ''
        """
    )

    op.alter_column("customers", "person_type", nullable=False)
    op.alter_column("customers", "address", nullable=False)


def downgrade() -> None:
    op.drop_column("customers", "address")
    op.drop_column("customers", "person_type")
