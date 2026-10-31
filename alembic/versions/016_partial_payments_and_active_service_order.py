"""support partial payments and one active service order per vehicle

Revision ID: 016
Revises: 015
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ACTIVE_SERVICE_ORDER_STATUSES = (
    "'Recebida', 'Em diagnóstico', 'Aguardando aprovação', "
    "'Aguardando início', 'Aguardando compra', 'Em execução', 'Finalizada'"
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'Parcialmente paga'"
            )

    if dialect == "sqlite":
        with op.batch_alter_table("invoices") as batch_op:
            batch_op.alter_column(
                "amount",
                existing_type=sa.Float(),
                type_=sa.Numeric(12, 2),
            )
    else:
        op.alter_column(
            "invoices",
            "amount",
            existing_type=sa.Float(),
            type_=sa.Numeric(12, 2),
            postgresql_using="amount::numeric(12,2)",
        )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "invoice_id",
            sa.Integer(),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "method",
            sa.Enum(
                "DINHEIRO",
                "CARTAO",
                "PIX",
                "TRANSFERENCIA",
                name="paymentmethod",
            ),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payments_positive_amount"),
        sa.UniqueConstraint(
            "invoice_id",
            "idempotency_key",
            name="uq_payments_invoice_idempotency_key",
        ),
    )
    op.create_index(
        "ix_payments_invoice_id",
        "payments",
        ["invoice_id"],
    )
    op.create_index(
        "uq_service_orders_active_vehicle",
        "service_orders",
        ["vehicle_id"],
        unique=True,
        sqlite_where=sa.text(
            f"status IN ({ACTIVE_SERVICE_ORDER_STATUSES})"
        ),
        postgresql_where=sa.text(
            f"status IN ({ACTIVE_SERVICE_ORDER_STATUSES})"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_service_orders_active_vehicle", table_name="service_orders")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_table("payments")
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("invoices") as batch_op:
            batch_op.alter_column(
                "amount",
                existing_type=sa.Numeric(12, 2),
                type_=sa.Float(),
            )
    else:
        op.alter_column(
            "invoices",
            "amount",
            existing_type=sa.Numeric(12, 2),
            type_=sa.Float(),
            postgresql_using="amount::double precision",
        )
