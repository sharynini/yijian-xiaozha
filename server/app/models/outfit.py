# -*- coding: utf-8 -*-
"""
搭配模型：对应 outfit 表 与 outfit_item 关系表
"""
from datetime import datetime

from app.extensions import db


class Outfit(db.Model):
    __tablename__ = 'outfit'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    user_id = db.Column(db.BigInteger, nullable=False, index=True, comment='所属用户ID')
    name = db.Column(db.String(100), nullable=True, comment='搭配名称（可选）')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
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

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    outfit_id = db.Column(db.BigInteger, nullable=False, index=True, comment='搭配方案ID')
    item_id = db.Column(db.BigInteger, nullable=False, index=True, comment='衣物ID')

    def __repr__(self):
        return f'<OutfitItem outfit={self.outfit_id} item={self.item_id}>'
