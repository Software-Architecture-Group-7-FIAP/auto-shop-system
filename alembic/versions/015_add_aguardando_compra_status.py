"""add the waiting-for-purchase service-order status

Revision ID: 015
Revises: 014
"""

from typing import Sequence, Union

from alembic import op


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE serviceorderstatus ADD VALUE IF NOT EXISTS 'Aguardando compra'"
        )


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in a reversible migration.
    pass
