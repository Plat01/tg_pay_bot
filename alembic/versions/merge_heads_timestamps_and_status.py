"""merge heads: convert_timestamps_timezone and add_expired_and_paid_status

Revision ID: merge_heads_timestamps_status
Revises: convert_timestamps_timezone, add_expired_and_paid_status
Create Date: 2026-04-13 23:42:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "merge_heads_timestamps_status"
down_revision: Union[str, Sequence[str], None] = (
    "convert_timestamps_timezone",
    "add_expired_and_paid_status",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
