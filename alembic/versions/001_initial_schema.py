"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, index=True),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255)),
        sa.Column("document", sa.String(14), unique=True, index=True),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255)),
        sa.Column("document", sa.String(14), unique=True),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id")),
        sa.Column("plate", sa.String(10), unique=True, index=True),
        sa.Column("brand", sa.String(100)),
        sa.Column("model", sa.String(100)),
        sa.Column("year", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255)),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(50), unique=True),
        sa.Column("unit_price", sa.Float()),
        sa.Column("stock_quantity", sa.Integer(), default=0),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255)),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_price", sa.Float()),
        sa.Column("estimated_hours", sa.Float(), default=1.0),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "service_product_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.Column("quantity", sa.Integer(), default=1),
    )
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id")),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id")),
        sa.Column("status", sa.Enum("Rascunho", "Enviado", "Aprovado", "Recusado", name="budgetstatus")),
        sa.Column("total_price", sa.Float(), default=0.0),
        sa.Column("estimated_delivery", sa.DateTime(), nullable=True),
        sa.Column("approval_token", sa.String(255), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "budget_service_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("budget_id", sa.Integer(), sa.ForeignKey("budgets.id")),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id")),
        sa.Column("quantity", sa.Integer(), default=1),
        sa.Column("unit_price", sa.Float()),
    )
    op.create_table(
        "budget_product_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("budget_id", sa.Integer(), sa.ForeignKey("budgets.id")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.Column("quantity", sa.Integer(), default=1),
        sa.Column("unit_price", sa.Float()),
        sa.Column("from_service", sa.Boolean(), default=False),
    )
    op.create_table(
        "service_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("budget_id", sa.Integer(), sa.ForeignKey("budgets.id"), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id")),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id")),
        sa.Column(
            "status",
            sa.Enum(
                "Recebida",
                "Em diagnóstico",
                "Aguardando aprovação",
                "Em execução",
                "Finalizada",
                "Entregue",
                name="serviceorderstatus",
            ),
        ),
        sa.Column(
            "priority",
            sa.Enum("Baixa", "Normal", "Alta", "Urgente", name="priority"),
        ),
        sa.Column("mechanic_name", sa.String(255), nullable=True),
        sa.Column("total_price", sa.Float(), default=0.0),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "service_order_service_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_order_id", sa.Integer(), sa.ForeignKey("service_orders.id")),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id")),
        sa.Column("quantity", sa.Integer(), default=1),
        sa.Column("unit_price", sa.Float()),
    )
    op.create_table(
        "service_order_product_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_order_id", sa.Integer(), sa.ForeignKey("service_orders.id")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.Column("quantity", sa.Integer(), default=1),
        sa.Column("unit_price", sa.Float()),
    )
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_order_id", sa.Integer(), sa.ForeignKey("service_orders.id")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.Column("quantity", sa.Integer()),
        sa.Column(
            "status",
            sa.Enum("Ativa", "Liberada", "Consumida", name="reservationstatus"),
        ),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("service_order_id", sa.Integer(), sa.ForeignKey("service_orders.id"), nullable=True),
        sa.Column("quantity", sa.Integer()),
        sa.Column(
            "status",
            sa.Enum("Pendente", "Pedido", "Recebido", name="purchaserequeststatus"),
        ),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_request_id", sa.Integer(), sa.ForeignKey("purchase_requests.id")),
        sa.Column("quantity", sa.Integer()),
        sa.Column("received_at", sa.DateTime()),
    )
    op.create_table(
        "stock_withdrawals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_order_id", sa.Integer(), sa.ForeignKey("service_orders.id")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.Column("quantity", sa.Integer()),
        sa.Column(
            "status",
            sa.Enum("Pendente", "Atendida", "Cancelada", name="stockwithdrawalstatus"),
        ),
        sa.Column("requested_at", sa.DateTime()),
        sa.Column("fulfilled_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_order_id", sa.Integer(), sa.ForeignKey("service_orders.id"), unique=True),
        sa.Column("amount", sa.Float()),
        sa.Column("status", sa.Enum("Pendente", "Paga", name="invoicestatus")),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    for table in [
        "invoices",
        "stock_withdrawals",
        "goods_receipts",
        "purchase_requests",
        "reservations",
        "service_order_product_lines",
        "service_order_service_lines",
        "service_orders",
        "budget_product_lines",
        "budget_service_lines",
        "budgets",
        "service_product_lines",
        "services",
        "products",
        "vehicles",
        "suppliers",
        "customers",
        "users",
    ]:
        op.drop_table(table)
