# -*- coding: utf-8 -*-
"""
衣物模型：对应 item 表
"""
from datetime import datetime

from app.extensions import db


class Item(db.Model):
    __tablename__ = 'item'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    user_id = db.Column(db.BigInteger, nullable=False, index=True, comment='所属用户ID')
    image_url = db.Column(db.String(500), nullable=False, comment='衣物照片URL')
    type = db.Column(db.String(20), nullable=False, comment='类型：上装/下装/外套/鞋子/配饰')
    color = db.Column(db.String(20), nullable=True, comment='颜色')
    season = db.Column(db.String(10), nullable=True, comment='适用季节：春/夏/秋/冬/全季')
    occasion = db.Column(db.String(20), nullable=True, comment='适用场合：日常/工作/运动/正式')
    material = db.Column(db.String(50), nullable=True, comment='材质')
    brand = db.Column(db.String(50), nullable=True, comment='品牌')
    price = db.Column(db.Numeric(10, 2), nullable=True, comment='购买价格（元）')
    purchase_date = db.Column(db.Date, nullable=True, comment='购买日期')
    status = db.Column(db.String(20), nullable=False, default='正常', comment='状态：正常/洗衣中/收纳中')
    remark = db.Column(db.Text, nullable=True, comment='备注')
    wear_count = db.Column(db.Integer, nullable=False, default=0, comment='累计穿着次数')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    deleted_at = db.Column(db.DateTime, nullable=True, comment='软删除时间')

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        """返回可暴露给前端的字段"""
        return {
            'item_id': self.id,
            'user_id': self.user_id,
            'image_url': self.image_url,
            'type': self.type,
            'color': self.color,
            'season': self.season,
            'occasion': self.occasion,
            'material': self.material,
            'brand': self.brand,
            'price': float(self.price) if self.price is not None else None,
            'purchase_date': self.purchase_date.strftime('%Y-%m-%d') if self.purchase_date else None,
            'status': self.status,
            'remark': self.remark,
            'wear_count': self.wear_count,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Item {self.id} {self.type}>'
