# -*- coding: utf-8 -*-
"""
穿搭日记模型：对应 wear_log 表
"""
from datetime import datetime

from app.common.media import to_public_url
from app.extensions import db

# 可选心情枚举（与 schema 注释一致）
ALLOWED_MOODS = {'开心', '平静', '专注', '疲惫', '期待', '低落', '自信', '随性'}


class WearLog(db.Model):
    __tablename__ = 'wear_log'
    # 表结构（索引名、外键、注释）与 schema.sql / 线上 MySQL 保持一致，迁移工具以此为准
    __table_args__ = (
        db.Index('idx_user_id', 'user_id'),
        db.Index('idx_outfit_id', 'outfit_id'),
        db.Index('idx_wear_date', 'wear_date'),
        db.Index('idx_deleted_at', 'deleted_at'),
        db.Index('idx_user_date', 'user_id', 'wear_date'),
        db.Index('idx_user_deleted', 'user_id', 'deleted_at'),
        {'comment': '穿搭日记表'},
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id', name='fk_wl_user', ondelete='CASCADE'),
                        nullable=False, comment='所属用户ID')
    outfit_id = db.Column(db.BigInteger, db.ForeignKey('outfit.id', name='fk_wl_outfit', ondelete='SET NULL'),
                          nullable=True, comment='已保存搭配ID；日记主路径用 item_ids 写快照，此时为 NULL')
    wear_date = db.Column(db.Date, nullable=False, comment='穿搭日期')
    mood = db.Column(db.String(10), nullable=True, comment='心情：开心/平静/专注/疲惫/期待/低落/自信/随性')
    content = db.Column(db.String(500), nullable=True, comment='一句话日记（选填）')
    photo_url = db.Column(db.String(500), nullable=True, comment='现场照片URL（选填）')
    temperature = db.Column(db.Numeric(4, 1), nullable=True, comment='当日温度，如 25.5')
    weather = db.Column(db.String(20), nullable=True, comment='天气：晴/多云/阴/雨/雪等')
    items_snapshot = db.Column(db.JSON, nullable=True,
                               comment='当天衣物快照（item_id列表及当时信息），支持非outfit穿搭记录')
    collage = db.Column(db.JSON, nullable=True,
                        comment='手动搭配画布布局 [{item_id,x,y,w,z}]，x/y/w 为相对画布边长的 0~1 比例')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           server_default=db.text('CURRENT_TIMESTAMP'), comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
                           server_default=db.text('CURRENT_TIMESTAMP'), comment='更新时间')
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
            'photo_url': to_public_url(self.photo_url),
            'temperature': float(self.temperature) if self.temperature is not None else None,
            'weather': self.weather,
            'items': self._snapshot_for_output(),
            'collage': self.collage or None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }

    def _snapshot_for_output(self) -> list:
        """快照里的图片地址同样转成完整地址（复制一份，不改动库里的数据）"""
        result = []
        for entry in self.items_snapshot or []:
            if isinstance(entry, dict):
                entry = {**entry, 'image_url': to_public_url(entry.get('image_url'))}
            result.append(entry)
        return result

    def __repr__(self):
        return f'<WearLog {self.id} {self.wear_date}>'
