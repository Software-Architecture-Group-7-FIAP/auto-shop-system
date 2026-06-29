"""normalize customer documents

Revision ID: 003
Revises: 002
Create Date: 2026-06-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "customer_documents" not in tables:
        op.create_table(
            "customer_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE")),
            sa.Column("document", sa.String(14), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    indexes = {
        index["name"] for index in inspect(bind).get_indexes("customer_documents")
    }
    if "ix_customer_documents_document" not in indexes:
        op.create_index(
            "ix_customer_documents_document",
            "customer_documents",
            ["document"],
            unique=True,
        )
    if "ix_customer_documents_customer_id" not in indexes:
        op.create_index(
            "ix_customer_documents_customer_id",
            "customer_documents",
            ["customer_id"],
        )

    op.execute(
        """
        INSERT INTO customer_documents (customer_id, document, created_at)
        SELECT id, document, COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM customers
        WHERE document IS NOT NULL AND document != ''
        ON CONFLICT (document) DO NOTHING
        """
    )

    op.drop_index("ix_customers_document", table_name="customers")
    op.drop_column("customers", "document")
    op.drop_column("customers", "person_type")


def downgrade() -> None:
    op.add_column("customers", sa.Column("document", sa.String(14), nullable=True))
    op.add_column("customers", sa.Column("person_type", sa.String(2), nullable=True))

    op.execute(
        """
        UPDATE customers
        SET document = (
            SELECT document
            FROM customer_documents
            WHERE customer_documents.customer_id = customers.id
            ORDER BY customer_documents.id
            LIMIT 1
        )
        """
    )
    op.execute(
        """
        UPDATE customers
        SET person_type = CASE
            WHEN LENGTH(document) = 11 THEN 'PF'
            WHEN LENGTH(document) = 14 THEN 'PJ'
            ELSE 'PF'
        END
        """
    )

    op.alter_column("customers", "document", nullable=False)
    op.alter_column("customers", "person_type", nullable=False)
    op.create_index("ix_customers_document", "customers", ["document"], unique=True)

    op.drop_index("ix_customer_documents_customer_id", table_name="customer_documents")
    op.drop_index("ix_customer_documents_document", table_name="customer_documents")
    op.drop_table("customer_documents")
