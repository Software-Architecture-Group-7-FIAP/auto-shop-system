"""Compatibility placeholder for databases already stamped as revision 007.

Revision ID: 007
Revises: 006
Create Date: 2026-06-30
"""

from typing import Sequence, Union


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
