"""add subscription products

Revision ID: add_subscription_products
Revises: convert_timestamps_timezone
Create Date: 2026-04-09 18:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "add_subscription_products"
down_revision: Union[str, None] = "convert_timestamps_timezone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add subscription products: monthly, quarterly, yearly
    # Note: happ_link is empty - will be filled by user via bot admin interface

    conn = op.get_bind()

    # Insert monthly product (1 month, 50₽ test price, 30 days)
    conn.execute(
        text("""
            INSERT INTO products (id, subscription_type, price, duration_days, device_limit, is_active, happ_link, created_at, updated_at)
            VALUES (
                gen_random_uuid(),
                'monthly',
                50.00,
                30,
                1,
                true,
                '',
                NOW(),
                NOW()
            )
        """)
    )

    # Insert quarterly product (3 months, 799₽, 90 days)
    conn.execute(
        text("""
            INSERT INTO products (id, subscription_type, price, duration_days, device_limit, is_active, happ_link, created_at, updated_at)
            VALUES (
                gen_random_uuid(),
                'quarterly',
                799.00,
                90,
                1,
                true,
                '',
                NOW(),
                NOW()
            )
        """)
    )

    # Insert yearly product (12 months, 2499₽, 365 days)
    conn.execute(
        text("""
            INSERT INTO products (id, subscription_type, price, duration_days, device_limit, is_active, happ_link, created_at, updated_at)
            VALUES (
                gen_random_uuid(),
                'yearly',
                2499.00,
                365,
                1,
                true,
                '',
                NOW(),
                NOW()
            )
        """)
    )

    print("✅ Added 3 subscription products: monthly, quarterly, yearly")


def downgrade() -> None:
    # Remove subscription products
    conn = op.get_bind()

    conn.execute(
        text("""
            DELETE FROM products 
            WHERE subscription_type IN ('monthly', 'quarterly', 'yearly')
        """)
    )

    print("✅ Removed subscription products: monthly, quarterly, yearly")
