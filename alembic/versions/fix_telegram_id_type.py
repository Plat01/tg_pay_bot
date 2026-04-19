"""fix telegram_id type to string

Revision ID: fix_telegram_id_type
Revises: 26bb232d826c
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_telegram_id_type'
down_revision: Union[str, None] = '26bb232d826c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change telegram_id from Integer to String (VARCHAR)
    # Using VARCHAR(50) to accommodate Telegram IDs as strings
    op.alter_column(
        'users',
        'telegram_id',
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Revert telegram_id back to Integer
    op.alter_column(
        'users',
        'telegram_id',
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        existing_nullable=False,
    )
