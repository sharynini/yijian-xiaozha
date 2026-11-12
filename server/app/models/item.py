# -*- coding: utf-8 -*-
"""
衣物模型：对应 item 表
"""
from datetime import datetime

from app.common.media import to_public_url
from app.extensions import db

# 内部类别：批量上传时 AI 未能识别类别的衣物先存为「未分类」，必须同时处于待确认状态，
# 不出现在用户可选的类别里，也不参与推荐
UNCLASSIFIED_TYPE = '未分类'


class Item(db.Model):
    __tablename__ = 'item'
    # 表结构（索引名、外键、注释）与 schema.sql / 线上 MySQL 保持一致，迁移工具以此为准
    __table_args__ = (
        db.Index('idx_user_id', 'user_id'),
        db.Index('idx_type', 'type'),
        db.Index('idx_season', 'season'),
        db.Index('idx_color', 'color'),
        db.Index('idx_status', 'status'),
        db.Index('idx_deleted_at', 'deleted_at'),
        db.Index('idx_user_deleted', 'user_id', 'deleted_at'),
        db.Index('idx_user_review', 'user_id', 'needs_review'),
        {'comment': '衣物表'},
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id', name='fk_item_user', ondelete='CASCADE'),
                        nullable=False, comment='所属用户ID')
    image_url = db.Column(db.String(500), nullable=False, comment='衣物照片URL')
    type = db.Column(db.String(20), nullable=False, comment='类型：上装/下装/外套/鞋子/配饰等')
    color = db.Column(db.String(20), nullable=True, comment='颜色')
    season = db.Column(db.String(10), nullable=True, comment='适用季节：春/夏/秋/冬/全季')
    occasion = db.Column(db.String(20), nullable=True, comment='适用场合：日常/工作/运动/正式等')
    material = db.Column(db.String(50), nullable=True, comment='材质')
    brand = db.Column(db.String(50), nullable=True, comment='品牌')
    price = db.Column(db.Numeric(10, 2), nullable=True, comment='购买价格（元）')
    purchase_date = db.Column(db.Date, nullable=True, comment='购买日期')
    status = db.Column(db.String(20), nullable=False, default='正常', server_default='正常', comment='状态：正常/洗衣中/收纳中')
    remark = db.Column(db.Text, nullable=True, comment='备注')
    wear_count = db.Column(db.Integer, nullable=False, default=0, server_default='0', comment='累计穿着次数')
    needs_review = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text('0'),
                             comment='是否待确认：批量上传后 AI 自动填写、用户尚未核对')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           server_default=db.text('CURRENT_TIMESTAMP'), comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
                           server_default=db.text('CURRENT_TIMESTAMP'), comment='更新时间')
    deleted_at = db.Column(db.DateTime, nullable=True, comment='软删除时间')

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        """返回可暴露给前端的字段"""
        return {
            'item_id': self.id,
            'user_id': self.user_id,
            'image_url': to_public_url(self.image_url),
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
            'needs_review': bool(self.needs_review),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Item {self.id} {self.type}>'
