# -*- coding: utf-8 -*-
"""
测试路由：验证服务可运行、数据库可连接
"""
from flask import Blueprint
from sqlalchemy import text

from app.common.response import success, error
from app.extensions import db

test_bp = Blueprint('test', __name__)


@test_bp.get('/ping')
def ping():
    """服务存活检查：GET /api/v1/test/ping"""
    return success(data={'message': 'pong'})


@test_bp.get('/db')
def db_check():
    """数据库连接检查：GET /api/v1/test/db"""
    try:
        db.session.execute(text('SELECT 1'))
        return success(data={'database': 'connected'})
    except Exception as e:
        return error(msg=f'数据库连接失败：{e}', code=500, http_status=500)
