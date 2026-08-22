"""Add vehicle location/color fields and per-customer plate uniqueness.

Revision ID: 009
Revises: 008
Create Date: 2026-06-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vehicles", sa.Column("state", sa.String(2), nullable=True))
    op.add_column("vehicles", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("vehicles", sa.Column("color", sa.String(50), nullable=True))

    op.execute(
        "UPDATE vehicles SET state = 'SP', city = 'Não informado', color = 'Não informado'"
    )

    op.alter_column("vehicles", "state", nullable=False)
    op.alter_column("vehicles", "city", nullable=False)
    op.alter_column("vehicles", "color", nullable=False)

    op.drop_index("ix_vehicles_plate", table_name="vehicles")
    op.create_index("ix_vehicles_plate", "vehicles", ["plate"], unique=False)
    op.create_unique_constraint(
        "uq_vehicles_customer_plate", "vehicles", ["customer_id", "plate"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_vehicles_customer_plate", "vehicles", type_="unique")
    op.drop_index("ix_vehicles_plate", table_name="vehicles")
    op.create_index("ix_vehicles_plate", "vehicles", ["plate"], unique=True)
    op.drop_column("vehicles", "color")
    op.drop_column("vehicles", "city")
    op.drop_column("vehicles", "state")
