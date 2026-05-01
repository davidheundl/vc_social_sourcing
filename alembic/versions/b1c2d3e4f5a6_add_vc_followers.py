"""add vc_followers table

Revision ID: b1c2d3e4f5a6
Revises: ca6047e32bda
Create Date: 2026-05-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'ca6047e32bda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'vc_followers',
        sa.Column('watcher_id', sa.String(64), nullable=False),
        sa.Column('follower_id', sa.String(64), nullable=False),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('watcher_id', 'follower_id'),
    )
    op.create_index('ix_vc_followers_first_seen', 'vc_followers', ['first_seen'])


def downgrade() -> None:
    op.drop_index('ix_vc_followers_first_seen', table_name='vc_followers')
    op.drop_table('vc_followers')
