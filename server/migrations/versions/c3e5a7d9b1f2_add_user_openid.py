"""add user openid, password_hash nullable

微信一键登录：
  - user.openid：小程序 openid，唯一（MySQL 唯一索引允许多个 NULL）
  - user.password_hash 改为可空：微信创建的账号没有密码

Revision ID: c3e5a7d9b1f2
Revises: a1a163ff1dc8
Create Date: 2026-11-05 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3e5a7d9b1f2'
down_revision = 'a1a163ff1dc8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('openid', sa.String(length=64), nullable=True,
                                      comment='微信小程序 openid；账号密码注册的用户为 NULL'))
        batch_op.create_unique_constraint('uk_openid', ['openid'])
        batch_op.alter_column('password_hash',
                              existing_type=sa.String(length=255),
                              nullable=True,
                              comment='密码哈希；微信登录创建的账号为 NULL',
                              existing_comment='密码哈希（如 bcrypt）')


def downgrade():
    # 注意：存在 password_hash 为 NULL 的微信账号时，改回 NOT NULL 会失败，需先处理这些行
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('password_hash',
                              existing_type=sa.String(length=255),
                              nullable=False,
                              comment='密码哈希（如 bcrypt）',
                              existing_comment='密码哈希；微信登录创建的账号为 NULL')
        batch_op.drop_constraint('uk_openid', type_='unique')
        batch_op.drop_column('openid')
