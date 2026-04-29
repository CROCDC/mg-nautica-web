"""add boat_videos table

Revision ID: 4b9e3f7a1d22
Revises: 1c67b00ed762
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '4b9e3f7a1d22'
down_revision = '3a8f2c1d0e45'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if 'boat_videos' not in tables:
        op.create_table(
            'boat_videos',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('boat_id', sa.Integer(), nullable=False),
            sa.Column('url', sa.String(length=500), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
            sa.ForeignKeyConstraint(['boat_id'], ['boats.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_boat_videos_boat_id', 'boat_videos', ['boat_id'])


def downgrade():
    op.drop_index('ix_boat_videos_boat_id', table_name='boat_videos')
    op.drop_table('boat_videos')
