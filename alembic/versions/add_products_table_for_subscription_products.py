"""add products table for subscription products

Revision ID: add_products_table
Revises: f3e8118b10a7
Create Date: 2026-04-08 05:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = "add_products_table"
down_revision: Union[str, None] = "f3e8118b10a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create products table
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_type", sa.VARCHAR(), nullable=False),
        sa.Column("price", sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("device_limit", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("happ_link", sa.VARCHAR(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_id"), "products", ["id"], unique=False)
    op.create_index(
        op.f("ix_products_subscription_type"), "products", ["subscription_type"], unique=False
    )

    # Add columns to subscriptions table
    op.add_column("subscriptions", sa.Column("product_id", sa.Uuid(), nullable=True))
    op.add_column("subscriptions", sa.Column("start_date", sa.DateTime(), nullable=True))

    # Populate start_date for existing subscriptions (using created_at as default)
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE subscriptions SET start_date = created_at WHERE start_date IS NULL")
    )

    # Make start_date non-nullable
    op.alter_column("subscriptions", "start_date", nullable=False)

    # Create foreign key constraint to products table
    op.create_foreign_key(
        "fk_subscriptions_product_id", "subscriptions", "products", ["product_id"], ["id"]
    )


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint("fk_subscriptions_product_id", "subscriptions", type_="foreignkey")

    # Remove columns from subscriptions
    op.drop_column("subscriptions", "start_date")
    op.drop_column("subscriptions", "product_id")

    # Drop products table
    op.drop_index(op.f("ix_products_subscription_type"), table_name="products")
    op.drop_index(op.f("ix_products_id"), table_name="products")
    op.drop_table("products")
