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


def _parse_pagination() -> tuple:
    """解析分页参数，非法值回退默认；per_page 最大 50"""
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get('per_page', 10))
    except (TypeError, ValueError):
        per_page = 10
    return max(page, 1), min(max(per_page, 1), 50)


@outfit_bp.post('')
@jwt_required()
def create_outfit():
    """
    创建搭配
    POST /api/outfits
    Body: { "item_ids": [1, 2, 3], "name": "周一通勤装"(选填，空则自动命名), "collage": [...](选填) }
    """
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}
    outfit = OutfitService.create(
        user_id=user_id,
        item_ids=data.get('item_ids'),
        name=data.get('name'),
        collage=data.get('collage'),
    )
    detail = OutfitService.get_detail(user_id=user_id, outfit_id=outfit.id)
    return success(data=detail, msg='搭配已保存')


@outfit_bp.get('')
@jwt_required()
def list_outfits():
    """
    我的搭配（分页，最近修改在前，不含早期遗留的无名临时搭配）
    GET /api/outfits?page=&per_page=
    """
    page, per_page = _parse_pagination()
    outfits, total = OutfitService.list_outfits(_current_user_id(), page=page, per_page=per_page)
    return success(data={'total': total, 'page': page, 'per_page': per_page, 'list': outfits})


@outfit_bp.get('/<int:outfit_id>')
@jwt_required()
def get_outfit(outfit_id: int):
    """
    获取搭配详情（含衣物列表）
    GET /api/outfits/<outfit_id>
    """
    return success(data=OutfitService.get_detail(user_id=_current_user_id(), outfit_id=outfit_id))


@outfit_bp.put('/<int:outfit_id>')
@jwt_required()
def update_outfit(outfit_id: int):
    """
    更新搭配（部分更新）
    PUT /api/outfits/<outfit_id>
    Body: { "name"?: "新名字", "item_ids"?: [...], "collage"?: [...] }
    """
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}
    OutfitService.update(user_id=user_id, outfit_id=outfit_id, data=data)
    return success(data=OutfitService.get_detail(user_id=user_id, outfit_id=outfit_id), msg='搭配已更新')


@outfit_bp.delete('/<int:outfit_id>')
@jwt_required()
def delete_outfit(outfit_id: int):
    """
    删除搭配（软删除，不影响已记录的日记）
    DELETE /api/outfits/<outfit_id>
    """
    OutfitService.delete(user_id=_current_user_id(), outfit_id=outfit_id)
    return success(msg='搭配已删除')
