"""create encrypted_subscriptions table

Revision ID: create_encrypted_subs
Revises: merge_heads_timestamps_and_status
Create Date: 2026-04-30 23:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision: str = "create_encrypted_subs"
down_revision: Union[str, None] = "merge_heads_timestamps_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "encrypted_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("public_id", sa.VARCHAR(length=100), nullable=False),
        sa.Column("encrypted_link", sa.VARCHAR(length=2000), nullable=False),
        sa.Column("vpn_sources_count", sa.Integer(), nullable=False),
        sa.Column("tags_used", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("behavior_json", sa.JSON(), nullable=True),
        sa.Column("ttl_hours", sa.Integer(), nullable=False),
        sa.Column("max_devices", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_encrypted_subscriptions_id"), "encrypted_subscriptions", ["id"], unique=False)
    op.create_index(
        op.f("ix_encrypted_subscriptions_subscription_id"),
        "encrypted_subscriptions",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_encrypted_subscriptions_public_id"),
        "encrypted_subscriptions",
        ["public_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_encrypted_subscription_subscription",
        "encrypted_subscriptions",
        "subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_encrypted_subscription_subscription",
        "encrypted_subscriptions",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_encrypted_subscriptions_public_id"), table_name="encrypted_subscriptions")
    op.drop_index(
        op.f("ix_encrypted_subscriptions_subscription_id"), table_name="encrypted_subscriptions"
    )
    op.drop_index(op.f("ix_encrypted_subscriptions_id"), table_name="encrypted_subscriptions")
    op.drop_table("encrypted_subscriptions")