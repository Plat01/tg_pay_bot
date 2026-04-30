"""add subscription_type and make product_id nullable

Revision ID: add_subscription_type_nullable_product
Revises: create_encrypted_subs
Create Date: 2026-04-30 23:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_subscription_type_nullable_product"
down_revision: Union[str, None] = "create_encrypted_subs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("subscription_type", sa.VARCHAR(length=50), nullable=True),
    )
    
    conn = op.get_bind()
    
    conn.execute(
        sa.text("""
            UPDATE subscriptions s
            SET subscription_type = p.subscription_type
            FROM products p
            WHERE s.product_id = p.id
        """)
    )
    
    op.alter_column("subscriptions", "product_id", nullable=True)


def downgrade() -> None:
    conn = op.get_bind()
    
    conn.execute(
        sa.text("""
            UPDATE subscriptions s
            SET product_id = p.id
            FROM products p
            WHERE s.subscription_type = p.subscription_type
            AND p.is_active = true
        """)
    )
    
    op.alter_column("subscriptions", "product_id", nullable=False)
    
    op.drop_column("subscriptions", "subscription_type")