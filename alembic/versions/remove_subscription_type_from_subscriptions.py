"""remove subscription_type and device_limit from subscriptions

Revision ID: remove_subscription_type
Revises: add_is_new_field
Create Date: 2026-04-08 07:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "remove_subscription_type"
down_revision: Union[str, None] = "add_is_new_field"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop subscription_type and device_limit - they're now taken from product via relationship
    op.drop_column("subscriptions", "subscription_type")
    op.drop_column("subscriptions", "device_limit")


def downgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column(
            "subscription_type",
            sa.VARCHAR(length=50),
            nullable=False,
            server_default="trial",
        ),
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "device_limit",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
