"""create tariff_settings table

Revision ID: create_tariff_settings
Revises: add_sub_type_nullable_product
Create Date: 2026-09-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "create_tariff_settings"
down_revision: str | None = "add_sub_type_nullable_product"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tariff_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tariff_type", sa.String(length=50), nullable=False),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_grant_days", sa.Integer(), nullable=True),
        sa.Column("duration_text", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("devices", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("label", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tariff_settings_id"), "tariff_settings", ["id"])
    op.create_index(
        op.f("ix_tariff_settings_tariff_type"), "tariff_settings", ["tariff_type"], unique=True
    )
    op.create_index(op.f("ix_tariff_settings_sort_order"), "tariff_settings", ["sort_order"])
    op.create_index(op.f("ix_tariff_settings_is_active"), "tariff_settings", ["is_active"])

    # Rows are seeded from DEFAULT_TARIFFS on bot startup (TariffService.initialize_cache).


def downgrade() -> None:
    op.drop_index(op.f("ix_tariff_settings_is_active"), table_name="tariff_settings")
    op.drop_index(op.f("ix_tariff_settings_sort_order"), table_name="tariff_settings")
    op.drop_index(op.f("ix_tariff_settings_tariff_type"), table_name="tariff_settings")
    op.drop_index(op.f("ix_tariff_settings_id"), table_name="tariff_settings")
    op.drop_table("tariff_settings")
