"""add service order tracking token hash

Revision ID: 008_service_order_tracking_token_hash
Revises: 007_repair_budget_product_lines_service_id
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa


revision = "008_service_order_tracking_token_hash"
down_revision = "007_repair_budget_product_lines_service_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_orders",
        sa.Column("tracking_token_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_service_orders_tracking_token_hash"),
        "service_orders",
        ["tracking_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_service_orders_tracking_token_hash"), table_name="service_orders")
    op.drop_column("service_orders", "tracking_token_hash")
