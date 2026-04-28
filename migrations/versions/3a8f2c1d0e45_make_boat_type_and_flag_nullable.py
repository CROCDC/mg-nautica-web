"""make boat_type and flag nullable

Revision ID: 3a8f2c1d0e45
Revises: 1c67b00ed762
Create Date: 2026-04-28 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '3a8f2c1d0e45'
down_revision = '1c67b00ed762'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("boats", schema=None) as batch_op:
        batch_op.alter_column("boat_type", existing_type=sa.String(50), nullable=True)
        batch_op.alter_column("flag", existing_type=sa.String(50), nullable=True)


def downgrade():
    with op.batch_alter_table("boats", schema=None) as batch_op:
        batch_op.alter_column("boat_type", existing_type=sa.String(50), nullable=False)
        batch_op.alter_column("flag", existing_type=sa.String(50), nullable=False)
