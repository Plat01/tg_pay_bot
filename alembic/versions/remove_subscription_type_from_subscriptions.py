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
    # Check if columns exist before dropping (they might have been manually removed)
    conn = op.get_bind()

    # Check subscription_type
    result = conn.execute(
        sa.text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'subscription_type'
        """)
    )
    if result.fetchone():
        op.drop_column("subscriptions", "subscription_type")

    # Check device_limit
    result = conn.execute(
        sa.text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'device_limit'
        """)
    )
    if result.fetchone():
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
