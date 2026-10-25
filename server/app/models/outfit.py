# -*- coding: utf-8 -*-
"""
搭配模型：对应 outfit 表 与 outfit_item 关系表
"""
from datetime import datetime

from app.extensions import db


class Outfit(db.Model):
    __tablename__ = 'outfit'
    # 表结构（索引名、外键、注释）与 schema.sql / 线上 MySQL 保持一致，迁移工具以此为准
    __table_args__ = (
        db.Index('idx_user_id', 'user_id'),
        db.Index('idx_deleted_at', 'deleted_at'),
        db.Index('idx_user_deleted', 'user_id', 'deleted_at'),
        {'comment': '搭配方案表'},
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id', name='fk_outfit_user', ondelete='CASCADE'),
                        nullable=False, comment='所属用户ID')
    name = db.Column(db.String(100), nullable=True, comment='搭配名称（可选）')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           server_default=db.text('CURRENT_TIMESTAMP'), comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
                           server_default=db.text('CURRENT_TIMESTAMP'), comment='更新时间')
    deleted_at = db.Column(db.DateTime, nullable=True, comment='软删除时间')

    def to_dict(self) -> dict:
        """基础字段（不含衣物列表）"""
        return {
            'outfit_id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }

    def __repr__(self):
        return f'<Outfit {self.id} {self.name}>'


class OutfitItem(db.Model):
    __tablename__ = 'outfit_item'
    # 表结构（索引名、外键、注释）与 schema.sql / 线上 MySQL 保持一致，迁移工具以此为准
    __table_args__ = (
        db.UniqueConstraint('outfit_id', 'item_id', name='uk_outfit_item'),
        db.Index('idx_outfit_id', 'outfit_id'),
        db.Index('idx_item_id', 'item_id'),
        {'comment': '搭配-衣物多对多关系表'},
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    outfit_id = db.Column(db.BigInteger, db.ForeignKey('outfit.id', name='fk_oi_outfit', ondelete='CASCADE'),
                          nullable=False, comment='搭配方案ID')
    item_id = db.Column(db.BigInteger, db.ForeignKey('item.id', name='fk_oi_item', ondelete='CASCADE'),
                        nullable=False, comment='衣物ID')

    def __repr__(self):
        return f'<OutfitItem outfit={self.outfit_id} item={self.item_id}>'
