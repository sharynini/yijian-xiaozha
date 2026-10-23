# -*- coding: utf-8 -*-
"""
用户模型：对应 user 表
"""
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    username = db.Column(db.String(50), unique=True, nullable=False, comment='登录用户名')
    email = db.Column(db.String(100), unique=True, nullable=True, comment='邮箱地址')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希')
    nickname = db.Column(db.String(50), nullable=True, comment='用户昵称')
    avatar = db.Column(db.String(500), nullable=True, comment='头像图片URL')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    deleted_at = db.Column(db.DateTime, nullable=True, comment='软删除时间')

    # ---------- 密码操作 ----------
    def set_password(self, raw_password: str) -> None:
        """明文密码 -> 哈希存储"""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """验证明文密码是否匹配"""
        return check_password_hash(self.password_hash, raw_password)

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        """返回可暴露给前端的安全字段"""
        return {
            'user_id': self.id,
            'username': self.username,
            'email': self.email,
            'nickname': self.nickname,
            'avatar': self.avatar,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }

    def __repr__(self):
        return f'<User {self.username}>'
