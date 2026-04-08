"""update subscriptions table with new fields

Revision ID: update_subscriptions_fields
Revises: add_products_table
Create Date: 2026-04-08 06:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "update_subscriptions_fields"
down_revision: Union[str, None] = "add_products_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # start_date and product_id already added in add_products_table migration
    # This migration only ensures product_id is populated for existing subscriptions

    conn = op.get_bind()

    # Make product_id non-nullable after migrating existing data
    # First, assign default product for existing subscriptions based on their type
    conn.execute(
        sa.text("""
        WITH default_products AS (
            SELECT id as product_id, subscription_type 
            FROM products 
            WHERE is_active = true
        )
        UPDATE subscriptions s
        SET product_id = dp.product_id
        FROM default_products dp
        WHERE s.product_id IS NULL 
        AND s.subscription_type = dp.subscription_type
    """)
    )

    # Make product_id non-nullable (but have to drop and recreate foreign key)
    op.drop_constraint("fk_subscriptions_product_id", "subscriptions", type_="foreignkey")
    op.alter_column("subscriptions", "product_id", nullable=False)
    op.create_foreign_key(
        "fk_subscriptions_product_id", "subscriptions", "products", ["product_id"], ["id"]
    )


def downgrade() -> None:
    # Reverse the changes
    op.drop_constraint("fk_subscriptions_product_id", "subscriptions", type_="foreignkey")
    op.alter_column("subscriptions", "product_id", nullable=True)
    op.create_foreign_key(
        "fk_subscriptions_product_id", "subscriptions", "products", ["product_id"], ["id"]
    )
