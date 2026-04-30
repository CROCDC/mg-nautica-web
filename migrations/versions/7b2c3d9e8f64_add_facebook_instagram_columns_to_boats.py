"""add facebook/instagram columns to boats

Revision ID: 7b2c3d9e8f64
Revises: 6a1f2b8c3e57
Create Date: 2026-04-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7b2c3d9e8f64'
down_revision = '6a1f2b8c3e57'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("boats")}

    new_cols = [
        ("facebook_post_id",    sa.String(80)),
        ("facebook_permalink",  sa.String(500)),
        ("facebook_synced_at",  sa.DateTime()),
        ("instagram_post_id",   sa.String(80)),
        ("instagram_permalink", sa.String(500)),
        ("instagram_synced_at", sa.DateTime()),
    ]
    with op.batch_alter_table("boats", schema=None) as batch_op:
        for col_name, col_type in new_cols:
            if col_name not in existing:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))


def downgrade():
    with op.batch_alter_table("boats", schema=None) as batch_op:
        batch_op.drop_column("instagram_synced_at")
        batch_op.drop_column("instagram_permalink")
        batch_op.drop_column("instagram_post_id")
        batch_op.drop_column("facebook_synced_at")
        batch_op.drop_column("facebook_permalink")
        batch_op.drop_column("facebook_post_id")
