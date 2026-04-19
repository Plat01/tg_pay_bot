"""convert timestamps to with timezone

Revision ID: convert_timestamps_timezone
Revises: update_subscriptions_fields
Create Date: 2026-04-08 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "convert_timestamps_timezone"
down_revision: Union[str, None] = "remove_subscription_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert all TIMESTAMP columns to TIMESTAMP WITH TIME ZONE
    # Users table
    op.execute(
        "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE USING updated_at AT TIME ZONE 'UTC'"
    )

    # Payments table
    op.execute(
        "ALTER TABLE payments ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE payments ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE USING updated_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE payments ALTER COLUMN completed_at TYPE TIMESTAMP WITH TIME ZONE USING completed_at AT TIME ZONE 'UTC'"
    )

    # Subscriptions table
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN start_date TYPE TIMESTAMP WITH TIME ZONE USING start_date AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN end_date TYPE TIMESTAMP WITH TIME ZONE USING end_date AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE USING updated_at AT TIME ZONE 'UTC'"
    )

    # Products table
    op.execute(
        "ALTER TABLE products ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE products ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE USING updated_at AT TIME ZONE 'UTC'"
    )

    # Referral earnings table
    op.execute(
        "ALTER TABLE referral_earnings ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE referral_earnings ALTER COLUMN paid_at TYPE TIMESTAMP WITH TIME ZONE USING paid_at AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    # Revert all TIMESTAMP WITH TIME ZONE columns back to TIMESTAMP WITHOUT TIME ZONE
    # Users table
    op.execute(
        "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE USING updated_at AT TIME ZONE 'UTC'"
    )

    # Payments table
    op.execute(
        "ALTER TABLE payments ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE payments ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE USING updated_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE payments ALTER COLUMN completed_at TYPE TIMESTAMP WITHOUT TIME ZONE USING completed_at AT TIME ZONE 'UTC'"
    )

    # Subscriptions table
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN start_date TYPE TIMESTAMP WITHOUT TIME ZONE USING start_date AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN end_date TYPE TIMESTAMP WITHOUT TIME ZONE USING end_date AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE USING updated_at AT TIME ZONE 'UTC'"
    )

    # Products table
    op.execute(
        "ALTER TABLE products ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE products ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE USING updated_at AT TIME ZONE 'UTC'"
    )

    # Referral earnings table
    op.execute(
        "ALTER TABLE referral_earnings ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE referral_earnings ALTER COLUMN paid_at TYPE TIMESTAMP WITHOUT TIME ZONE USING paid_at AT TIME ZONE 'UTC'"
    )
