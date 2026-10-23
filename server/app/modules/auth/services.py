# -*- coding: utf-8 -*-
"""
认证业务逻辑层
只处理业务规则，不处理 HTTP 请求/响应
"""
import re
from typing import Tuple

from flask_jwt_extended import create_access_token

from app.common.errors import ApiError
from app.extensions import db
from app.models.user import User

# 邮箱正则（RFC 5322 简化版）
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')


class AuthService:
    """注册 / 登录 / 用户信息"""

    # ---------------- 注册 ----------------
    @staticmethod
    def register(username: str, email: str, password: str) -> User:
        """
        用户注册
        :raises ApiError: 参数错误 / 用户名或邮箱已存在
        """
        # 1. 基础校验
        AuthService._validate_register_params(username, email, password)

        # 2. 唯一性校验（仅查未删除用户）
        if User.query.filter_by(username=username, deleted_at=None).first():
            raise ApiError('用户名已存在', code=1001)

        if User.query.filter_by(email=email, deleted_at=None).first():
            raise ApiError('邮箱已被注册', code=1002)

        # 3. 创建用户
        user = User(username=username, email=email, nickname=username)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()
        return user

    # ---------------- 登录 ----------------
    @staticmethod
    def login(account: str, password: str) -> Tuple[User, str]:
        """
        用户登录：支持用户名或邮箱
        :return: (用户对象, JWT access_token)
        :raises ApiError: 账号不存在或密码错误
        """
        if not account or not password:
            raise ApiError('账号和密码不能为空', code=1004)

        # 按用户名或邮箱查找（排除已删除用户）
        user = User.query.filter(
            db.or_(User.username == account, User.email == account),
            User.deleted_at.is_(None)
        ).first()

        if not user or not user.check_password(password):
            # 统一提示，不暴露具体是账号不存在还是密码错误
            raise ApiError('用户名或密码错误', code=1003)

        # 生成 JWT（identity 为 user.id）
        access_token = create_access_token(identity=str(user.id))
        return user, access_token

    # ---------------- 获取当前用户 ----------------
    @staticmethod
    def get_user_by_id(user_id: int) -> User:
        """
        按 ID 查询有效用户
        :raises ApiError: 用户不存在或已删除
        """
        user = User.query.filter_by(id=user_id, deleted_at=None).first()
        if not user:
            raise ApiError('用户不存在或已被删除', code=1005)
        return user

    # ---------------- 内部校验 ----------------
    @staticmethod
    def _validate_register_params(username: str, email: str, password: str) -> None:
        """注册参数校验"""
        if not username or not username.strip():
            raise ApiError('用户名不能为空', code=1004)

        username = username.strip()
        if len(username) < 2 or len(username) > 20:
            raise ApiError('用户名长度需为 2-20 个字符', code=1004)

        if not email or not email.strip():
            raise ApiError('邮箱不能为空', code=1004)

        email = email.strip()
        if not EMAIL_PATTERN.match(email):
            raise ApiError('邮箱格式不正确', code=1004)

        if not password:
            raise ApiError('密码不能为空', code=1004)

        if len(password) < 6:
            raise ApiError('密码长度至少为 6 位', code=1004)
