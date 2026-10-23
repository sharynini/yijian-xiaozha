# -*- coding: utf-8 -*-
"""
穿搭日记模型：对应 wear_log 表
"""
from datetime import datetime

from app.extensions import db

# 可选心情枚举（与 schema 注释一致）
ALLOWED_MOODS = {'开心', '平静', '专注', '疲惫', '期待', '低落', '自信', '随性'}


class WearLog(db.Model):
    __tablename__ = 'wear_log'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    user_id = db.Column(db.BigInteger, nullable=False, index=True, comment='所属用户ID')
    outfit_id = db.Column(db.BigInteger, nullable=True, index=True, comment='搭配方案ID，NULL表示临时组合')
    wear_date = db.Column(db.Date, nullable=False, index=True, comment='穿搭日期')
    mood = db.Column(db.String(10), nullable=True, comment='心情')
    content = db.Column(db.String(500), nullable=True, comment='一句话日记（选填）')
    photo_url = db.Column(db.String(500), nullable=True, comment='现场照片URL（选填）')
    temperature = db.Column(db.Numeric(4, 1), nullable=True, comment='当日温度')
    weather = db.Column(db.String(20), nullable=True, comment='天气')
    items_snapshot = db.Column(db.JSON, nullable=True, comment='当天衣物快照')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    deleted_at = db.Column(db.DateTime, nullable=True, comment='软删除时间')

    def to_dict(self) -> dict:
        """返回字段，含衣物快照列表"""
        return {
            'log_id': self.id,
            'user_id': self.user_id,
            'outfit_id': self.outfit_id,
            'wear_date': self.wear_date.strftime('%Y-%m-%d') if self.wear_date else None,
            'mood': self.mood,
            'content': self.content,
            'photo_url': self.photo_url,
            'temperature': float(self.temperature) if self.temperature is not None else None,
            'weather': self.weather,
            'items': self.items_snapshot or [],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }

    def __repr__(self):
        return f'<WearLog {self.id} {self.wear_date}>'
