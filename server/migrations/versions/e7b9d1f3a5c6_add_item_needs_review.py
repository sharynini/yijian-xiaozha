"""add item needs_review

批量上传：衣物新增「待确认」标记 item.needs_review（布尔，默认 0），以及 (user_id, needs_review) 联合索引。
AI 未识别出类别的衣物以内部类别「未分类」入库，必须处于待确认状态（由业务层校验，表结构无需变化）。

Revision ID: e7b9d1f3a5c6
Revises: d4f6b8a0c2e3
Create Date: 2026-11-11 17:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7b9d1f3a5c6'
down_revision = 'd4f6b8a0c2e3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('needs_review', sa.Boolean(), nullable=False, server_default=sa.text('0'),
                                      comment='是否待确认：批量上传后 AI 自动填写、用户尚未核对'))
        batch_op.create_index('idx_user_review', ['user_id', 'needs_review'], unique=False)


def downgrade():
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.drop_index('idx_user_review')
        batch_op.drop_column('needs_review')
