"""add last_login_at to users

Revision ID: 1c67b00ed762
Revises: 1f21900c91dd
Create Date: 2026-04-27 13:43:53.133439

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1c67b00ed762'
down_revision = '1f21900c91dd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('last_login_at')
