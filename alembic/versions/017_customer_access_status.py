"""add customer access status

Revision ID: 017
Revises: 016
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CUSTOMER_STATUSES = ("Ativo", "Inativo")
CUSTOMER_STATUS_ENUM_NAME = "customerstatus"


def _column_type(bind) -> sa.types.TypeEngine:
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *CUSTOMER_STATUSES,
            name=CUSTOMER_STATUS_ENUM_NAME,
            create_type=False,
        )
    return sa.String(length=max(map(len, CUSTOMER_STATUSES)))


def upgrade() -> None:
    bind = op.get_bind()
    column_type = _column_type(bind)

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            *CUSTOMER_STATUSES,
            name=CUSTOMER_STATUS_ENUM_NAME,
        ).create(bind, checkfirst=True)

    op.add_column(
        "customers",
        sa.Column(
            "status",
            column_type,
            nullable=True,
            server_default="Ativo",
        ),
    )
    op.execute("UPDATE customers SET status = 'Ativo' WHERE status IS NULL")

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("customers") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=column_type,
                nullable=False,
                server_default="Ativo",
            )
    else:
        op.alter_column(
            "customers",
            "status",
            existing_type=column_type,
            nullable=False,
            server_default="Ativo",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("customers") as batch_op:
            batch_op.drop_column("status")
    else:
        op.drop_column("customers", "status")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            *CUSTOMER_STATUSES,
            name=CUSTOMER_STATUS_ENUM_NAME,
        ).drop(bind, checkfirst=True)
