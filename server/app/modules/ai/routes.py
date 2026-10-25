# -*- coding: utf-8 -*-
"""
AI 路由层（均需 JWT）
POST /api/ai/recognize-item   Body: { "image_url": "上传接口返回的 url 或 path" }
POST /api/ai/cutout           Body: { "image_url": "..." }   去背景，返回新的透明 PNG 地址
"""
from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.common.response import success
from app.modules.ai.services import AiService, CutoutService

ai_bp = Blueprint('ai', __name__)


@ai_bp.post('/recognize-item')
@jwt_required()
def recognize_item():
    """
    识别衣物的类型 / 颜色 / 季节 / 场合
    返回: { type, color, season, occasion }，识别不出的项为 null
    """
    data = request.get_json(silent=True) or {}
    result = AiService.recognize_item(user_id=int(get_jwt_identity()), image_url=data.get('image_url'))
    return success(data=result)


@ai_bp.post('/cutout')
@jwt_required()
def cutout():
    """
    抠图：去掉背景，另存为透明 PNG（原图文件保留在磁盘上，是否替换由前端决定）
    返回: { url, path }
    """
    data = request.get_json(silent=True) or {}
    result = CutoutService.cutout(user_id=int(get_jwt_identity()), image_url=data.get('image_url'))
    return success(data=result, msg='抠图成功')
