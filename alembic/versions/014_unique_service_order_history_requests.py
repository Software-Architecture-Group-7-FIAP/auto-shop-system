"""make service-order history writes idempotent by request id

Revision ID: 014
Revises: 013
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # The old count+slice persistence could append the same request more than
    # once under a retry. Keep the first event for each request before adding
    # the constraint, so the migration is safe on already-used databases.
    bind.execute(
        sa.text(
            "DELETE FROM service_order_status_history "
            "WHERE id IN ("
            "SELECT duplicate.id FROM service_order_status_history AS duplicate "
            "WHERE duplicate.request_id IS NOT NULL AND EXISTS ("
            "SELECT 1 FROM service_order_status_history AS keeper "
            "WHERE keeper.service_order_id = duplicate.service_order_id "
            "AND keeper.request_id = duplicate.request_id "
            "AND keeper.id < duplicate.id)"
            ")"
        )
    )
    op.create_unique_constraint(
        "uq_service_order_status_history_request",
        "service_order_status_history",
        ["service_order_id", "request_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_service_order_status_history_request",
        "service_order_status_history",
        type_="unique",
    )
