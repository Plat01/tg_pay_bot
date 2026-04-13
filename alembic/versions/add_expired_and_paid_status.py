"""add EXPIRED and PAID to paymentstatus enum

Revision ID: add_expired_and_paid_status
Revises: remove_subscription_type
Create Date: 2026-04-13 23:37:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "add_expired_and_paid_status"
down_revision: Union[str, None] = "remove_subscription_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'PAID'")
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'EXPIRED'")


def downgrade() -> None:
    pass
