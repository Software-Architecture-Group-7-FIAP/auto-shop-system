"""replace public bearer token storage with expiring fingerprints

Revision ID: 010
Revises: 009
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE budgetstatus ADD VALUE IF NOT EXISTS 'Substituído'")
        op.execute("ALTER TYPE serviceorderstatus ADD VALUE IF NOT EXISTS 'Aguardando início'")
    duplicates = bind.execute(
        sa.text(
            "SELECT budget_id FROM service_orders "
            "WHERE budget_id IS NOT NULL GROUP BY budget_id HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        ids = ", ".join(str(row[0]) for row in duplicates)
        raise RuntimeError(
            f"Migration aborted: duplicate service orders for budget ids: {ids}. "
            "Reconcile these records before enabling the unique constraint."
        )

    bind.execute(
        sa.text(
            "UPDATE service_orders SET status = :received "
            "WHERE status = :waiting AND mechanic_name IS NULL"
        ),
        {"received": "Recebida", "waiting": "Aguardando aprovação"},
    )

    op.add_column("budgets", sa.Column("approval_token_hash", sa.String(64), nullable=True))
    op.add_column("budgets", sa.Column("approval_expires_at", sa.DateTime(), nullable=True))
    op.add_column("budgets", sa.Column("approval_used_at", sa.DateTime(), nullable=True))
    op.add_column(
        "budgets", sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("budgets", sa.Column("supersedes_budget_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_budgets_supersedes_budget_id", "budgets", "budgets", ["supersedes_budget_id"], ["id"]
    )
    op.create_index(
        "ix_budgets_approval_token_hash", "budgets", ["approval_token_hash"], unique=True
    )
    # Existing raw tokens are intentionally discarded. All links must be
    # reissued after this migration (cut-clean invalidation).
    op.drop_column("budgets", "approval_token")

    op.add_column(
        "service_orders", sa.Column("tracking_token_expires_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "service_orders", sa.Column("tracking_token_revoked_at", sa.DateTime(), nullable=True)
    )
    bind.execute(
        sa.text(
            "UPDATE service_orders SET tracking_token_revoked_at = CURRENT_TIMESTAMP "
            "WHERE tracking_token_hash IS NOT NULL"
        )
    )
    op.create_unique_constraint(
        "uq_service_orders_budget_id", "service_orders", ["budget_id"]
    )


def downgrade() -> None:
    """Refuse an unsafe rollback instead of partially corrupting the schema.

    Upgrade 010 intentionally invalidates raw approval and tracking tokens and
    adds PostgreSQL enum values that cannot be removed transactionally. There
    is therefore no data-preserving downgrade operation. Restore a database
    backup/snapshot taken before this migration, then run Alembic against that
    restored database.
    """
    raise RuntimeError(
        "Migration 010 is irreversible: restore a pre-010 database backup "
        "instead of running downgrade."
    )
