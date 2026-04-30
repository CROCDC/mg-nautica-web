"""add youtube columns to boats

Revision ID: 5c0d8e9f4a13
Revises: 4b9e3f7a1d22
Create Date: 2026-04-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '5c0d8e9f4a13'
down_revision = '4b9e3f7a1d22'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("boats")}

    new_cols = [
        ("youtube_video_id",  sa.String(20)),
        ("youtube_synced_at", sa.DateTime()),
    ]
    with op.batch_alter_table("boats", schema=None) as batch_op:
        for col_name, col_type in new_cols:
            if col_name not in existing:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))


def downgrade():
    with op.batch_alter_table("boats", schema=None) as batch_op:
        batch_op.drop_column("youtube_synced_at")
        batch_op.drop_column("youtube_video_id")
