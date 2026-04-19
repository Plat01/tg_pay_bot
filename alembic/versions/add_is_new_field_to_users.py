"""add is_new field to users

Revision ID: add_is_new_field
Revises: increase_link_size
Create Date: 2026-04-08 07:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_is_new_field"
down_revision: Union[str, None] = "increase_link_size"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_new", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("users", "is_new")
