"""add whatsapp_synced_at to boats

Revision ID: 6a1f2b8c3e57
Revises: 5c0d8e9f4a13
Create Date: 2026-04-29 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '6a1f2b8c3e57'
down_revision = '5c0d8e9f4a13'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("boats")}
    with op.batch_alter_table("boats", schema=None) as batch_op:
        if "whatsapp_synced_at" not in existing:
            batch_op.add_column(sa.Column("whatsapp_synced_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("boats", schema=None) as batch_op:
        batch_op.drop_column("whatsapp_synced_at")
