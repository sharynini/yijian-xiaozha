"""add item image_fp

重复照片检测：衣物新增图片指纹 item.image_fp（dHash + 颜色签名，可空）。
已有衣物的指纹用 `flask backfill-image-fp` 补算。

Revision ID: f2a4c6e8b0d2
Revises: e7b9d1f3a5c6
Create Date: 2026-11-12 16:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a4c6e8b0d2'
down_revision = 'e7b9d1f3a5c6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_fp', sa.String(length=120), nullable=True,
                                      comment='图片指纹（dHash:颜色签名），用于提示可能重复的衣物；外部图片或无法解析时为空'))


def downgrade():
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.drop_column('image_fp')
