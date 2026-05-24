"""add_item_history

Revision ID: f8a7b6c5d432
Revises: e5bf2f933716
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f8a7b6c5d432'
down_revision: Union[str, Sequence[str], None] = 'e5bf2f933716'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'item_history',
        sa.Column('id',         sa.String(36),  nullable=False),
        sa.Column('item_id',    sa.String(36),  nullable=True),
        sa.Column('item_name',  sa.String(255), nullable=False),
        sa.Column('action',     sa.String(50),  nullable=False),
        sa.Column('changes',    sa.JSON(),       nullable=True),
        sa.Column('user_id',    sa.String(36),  nullable=True),
        sa.Column('created_at', sa.DateTime(),  nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('item_history', schema=None) as batch_op:
        batch_op.create_index('ix_item_history_item_id',    ['item_id'],    unique=False)
        batch_op.create_index('ix_item_history_created_at', ['created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('item_history', schema=None) as batch_op:
        batch_op.drop_index('ix_item_history_created_at')
        batch_op.drop_index('ix_item_history_item_id')
    op.drop_table('item_history')
