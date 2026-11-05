# -*- coding: utf-8 -*-
"""
认证路由层
只负责接收请求、调用服务、返回响应，不写业务逻辑
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.common.response import success, error
from app.modules.auth.services import AuthService

auth_bp = Blueprint('auth', __name__)


@auth_bp.post('/register')
def register():
    """
    用户注册
    POST /api/auth/register
    Body: { "username": "xxx", "email": "xxx@xx.com", "password": "123456" }
    """
    data = request.get_json(silent=True) or {}

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    user = AuthService.register(username=username, email=email, password=password)

    return success(data=user.to_dict(), msg='注册成功')


@auth_bp.post('/login')
def login():
    """
    用户登录（支持用户名或邮箱）
    POST /api/auth/login
    Body: { "account": "xxx", "password": "123456" }
    """
    data = request.get_json(silent=True) or {}

    account = data.get('account', '').strip()
    password = data.get('password', '')

    user, access_token = AuthService.login(account=account, password=password)

    return success(data={
        'access_token': access_token,
        'user': user.to_dict(),
    }, msg='登录成功')


@auth_bp.post('/wx-login')
def wx_login():
    """
    微信小程序一键登录（openid 不存在则自动注册）
    POST /api/auth/wx-login
    Body: { "code": "wx.login 返回的 code" }
    返回: { access_token, user, is_new }
    """
    data = request.get_json(silent=True) or {}

    user, access_token, is_new = AuthService.wx_login(code=data.get('code'))

    return success(data={
        'access_token': access_token,
        'user': user.to_dict(),
        'is_new': is_new,
    }, msg='登录成功')


@auth_bp.get('/profile')
@jwt_required()
def profile():
    """
    获取当前登录用户信息
    GET /api/auth/profile
    Header: Authorization: Bearer <token>
    """
    current_user_id = int(get_jwt_identity())
    user = AuthService.get_user_by_id(current_user_id)

    return success(data=user.to_dict())


@auth_bp.delete('/account')
@jwt_required()
def delete_account():
    """
    注销账号：彻底删除当前用户的账号、衣物、搭配、日记和上传的图片，不可恢复
    DELETE /api/auth/account
    Header: Authorization: Bearer <token>
    """
    result = AuthService.delete_account(int(get_jwt_identity()))
    return success(data=result, msg='账号已注销')
