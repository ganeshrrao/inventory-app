"""add_user_email_to_history

Revision ID: a3c2d1e0f9b8
Revises: f8a7b6c5d432
Create Date: 2026-05-22 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3c2d1e0f9b8'
down_revision: Union[str, Sequence[str], None] = 'f8a7b6c5d432'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('item_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_email', sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('item_history', schema=None) as batch_op:
        batch_op.drop_column('user_email')
