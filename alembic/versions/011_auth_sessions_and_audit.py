"""add role-aware cookie sessions and service-order transition audit"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SERVICE_ORDER_STATUSES = (
    "Recebida",
    "Em diagnóstico",
    "Aguardando aprovação",
    "Aguardando início",
    "Em execução",
    "Finalizada",
    "Entregue",
)


def _existing_service_order_status_enum(bind) -> sa.types.TypeEngine:
    """Reference the serviceorderstatus type without trying to create it.

    ``create_type`` only exists on ``postgresql.ENUM``; ``sa.Enum`` silently
    discards it and the adapted native type emits a ``CREATE TYPE`` for a type
    that already exists.

    This only breaks on the path that matters. Upgrading an existing database
    (already at 010) runs this migration in a process where 001 never ran, so
    alembic's DDL-runner memo is empty and the duplicate ``CREATE TYPE`` is
    emitted: ``DuplicateObject: type "serviceorderstatus" already exists``.
    Building a database from scratch in one ``alembic upgrade head`` hides it,
    because 001 already registered the name in that shared memo.
    """
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *SERVICE_ORDER_STATUSES, name="serviceorderstatus", create_type=False
        )
    return sa.Enum(*SERVICE_ORDER_STATUSES, name="serviceorderstatus")


def upgrade() -> None:
    bind = op.get_bind()
    user_role = sa.Enum("ADMIN", "OPERATOR", name="userrole")
    if bind.dialect.name == "postgresql":
        user_role.create(bind, checkfirst=True)

    # Every pre-existing user is demoted to OPERATOR on purpose: roles are
    # granted explicitly, never inferred. Exactly one admin must be promoted
    # after this migration with `python -m src.scripts.promote_first_admin`,
    # otherwise no one can use the admin-only status override. See the
    # upgrade runbook in docs/security/security-report.md.
    op.add_column(
        "users",
        sa.Column("role", user_role, nullable=False, server_default="OPERATOR"),
    )

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_token_hash", "refresh_sessions", ["token_hash"], unique=True)
    op.create_index("ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"])

    op.create_table(
        "service_order_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_order_id", sa.Integer(), sa.ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", _existing_service_order_status_enum(bind), nullable=False),
        sa.Column("to_status", _existing_service_order_status_enum(bind), nullable=False),
        sa.Column("transition_type", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_service_order_status_history_service_order_id", "service_order_status_history", ["service_order_id"])
    op.create_index("ix_service_order_status_history_request_id", "service_order_status_history", ["request_id"])
    op.create_index("ix_service_order_status_history_occurred_at", "service_order_status_history", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_service_order_status_history_occurred_at", table_name="service_order_status_history")
    op.drop_index("ix_service_order_status_history_request_id", table_name="service_order_status_history")
    op.drop_index("ix_service_order_status_history_service_order_id", table_name="service_order_status_history")
    op.drop_table("service_order_status_history")
    op.drop_index("ix_refresh_sessions_family_id", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_token_hash", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_column("users", "role")
    if op.get_bind().dialect.name == "postgresql":
        sa.Enum("ADMIN", "OPERATOR", name="userrole").drop(op.get_bind(), checkfirst=True)
