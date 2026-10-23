# -*- coding: utf-8 -*-
"""
搭配路由层
只负责接收请求、调用服务、返回响应
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.common.response import success
from app.modules.outfit.services import OutfitService

outfit_bp = Blueprint('outfit', __name__)


def _current_user_id() -> int:
    return int(get_jwt_identity())


@outfit_bp.post('')
@jwt_required()
def create_outfit():
    """
    创建搭配
    POST /api/outfits
    Header: Authorization: Bearer <token>
    Body: { "item_ids": [1, 2, 3], "name": "周一通勤装"(可选) }
    """
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}

    outfit = OutfitService.create(
        user_id=user_id,
        item_ids=data.get('item_ids'),
        name=data.get('name'),
    )

    detail = OutfitService.get_detail(user_id=user_id, outfit_id=outfit.id)
    return success(data=detail, msg='搭配创建成功')


@outfit_bp.get('/<int:outfit_id>')
@jwt_required()
def get_outfit(outfit_id: int):
    """
    获取搭配详情（含衣物列表）
    GET /api/outfits/<outfit_id>
    Header: Authorization: Bearer <token>
    """
    user_id = _current_user_id()
    detail = OutfitService.get_detail(user_id=user_id, outfit_id=outfit_id)
    return success(data=detail)
