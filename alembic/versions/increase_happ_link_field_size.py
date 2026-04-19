"""increase happ_link field size

Revision ID: increase_link_size
Revises: update_subscriptions_fields
Create Date: 2026-04-08 06:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "increase_link_size"
down_revision: Union[str, None] = "update_subscriptions_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter the happ_link column to increase its size
    op.alter_column(
        "products",
        "happ_link",
        existing_type=sa.VARCHAR(length=500),
        type_=sa.VARCHAR(length=2000),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Revert the column size back to original
    op.alter_column(
        "products",
        "happ_link",
        existing_type=sa.VARCHAR(length=2000),
        type_=sa.VARCHAR(length=500),
        existing_nullable=False,
    )
