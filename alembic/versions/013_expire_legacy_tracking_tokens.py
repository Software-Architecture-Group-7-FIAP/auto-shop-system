"""expire legacy tracking tokens without an issuance TTL

Revision ID: 013
Revises: 012
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tokens issued before the TTL-at-issuance change must not remain valid
    # indefinitely. Customers can receive a fresh token by resending the OS.
    op.get_bind().execute(
        sa.text(
            "UPDATE service_orders "
            "SET tracking_token_expires_at = CURRENT_TIMESTAMP "
            "WHERE tracking_token_hash IS NOT NULL "
            "AND tracking_token_revoked_at IS NULL "
            "AND tracking_token_expires_at IS NULL"
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "Migration 013 is intentionally irreversible: legacy tracking tokens "
        "must not be made valid again by rollback."
    )
