"""add outfit collage

搭配方案保存画布布局：outfit.collage（JSON，可空）；同步 name 字段注释

Revision ID: d4f6b8a0c2e3
Revises: c3e5a7d9b1f2
Create Date: 2026-11-05 14:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4f6b8a0c2e3'
down_revision = 'c3e5a7d9b1f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('outfit', schema=None) as batch_op:
        batch_op.add_column(sa.Column('collage', sa.JSON(), nullable=True,
                                      comment='手动搭配画布布局 [{item_id,x,y,w,z}]，x/y/w 为相对画布边长的 0~1 比例'))
        batch_op.alter_column('name',
                              existing_type=sa.String(length=100),
                              existing_nullable=True,
                              comment='搭配名称；新建时未填会自动生成，NULL 为早期日记流程遗留的临时搭配',
                              existing_comment='搭配名称（可选）')


def downgrade():
    with op.batch_alter_table('outfit', schema=None) as batch_op:
        batch_op.alter_column('name',
                              existing_type=sa.String(length=100),
                              existing_nullable=True,
                              comment='搭配名称（可选）',
                              existing_comment='搭配名称；新建时未填会自动生成，NULL 为早期日记流程遗留的临时搭配')
        batch_op.drop_column('collage')
