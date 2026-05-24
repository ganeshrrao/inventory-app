"""add_created_by_email_to_items

Revision ID: b2e4f6a8c0d1
Revises: a3c2d1e0f9b8
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2e4f6a8c0d1'
down_revision: Union[str, Sequence[str], None] = 'a3c2d1e0f9b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_email', sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_column('created_by_email')
