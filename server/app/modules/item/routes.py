# -*- coding: utf-8 -*-
"""
衣物路由层
只负责接收请求、调用服务、返回响应，不写业务逻辑
所有接口均需 JWT 鉴权，只能操作当前登录用户自己的数据
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.common.response import success
from app.modules.item.services import ItemService

item_bp = Blueprint('item', __name__)

# 分页参数边界
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 50


def _current_user_id() -> int:
    """从 JWT 中取出当前用户 ID"""
    return int(get_jwt_identity())


def _parse_pagination() -> tuple:
    """解析并校验分页参数（非法值回退为默认）"""
    try:
        page = int(request.args.get('page', DEFAULT_PAGE))
    except (TypeError, ValueError):
        page = DEFAULT_PAGE
    try:
        per_page = int(request.args.get('per_page', DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE

    page = max(page, 1)
    per_page = min(max(per_page, 1), MAX_PER_PAGE)
    return page, per_page


def _parse_review_filter():
    """列表的 needs_review 筛选：1/true 只看待确认，0/false 只看已确认，其他值或不传则不筛选"""
    raw = (request.args.get('needs_review') or '').strip().lower()
    if raw in ('1', 'true'):
        return True
    if raw in ('0', 'false'):
        return False
    return None


@item_bp.post('')
@jwt_required()
def create_item():
    """
    添加衣物
    POST /api/items
    Header: Authorization: Bearer <token>
    Body: { image_url, type, color?, season?, occasion?, material?, brand?, price?, purchase_date?, status?, remark?,
            needs_review? }
    批量上传时传 needs_review=true；AI 没认出类别时 type 可传「未分类」（必须同时 needs_review=true）
    """
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}

    item = ItemService.create(user_id=user_id, data=data)
    return success(data=item.to_dict(), msg='添加成功')


@item_bp.get('')
@jwt_required()
def list_items():
    """
    获取衣物列表（筛选 + 分页）
    GET /api/items?type=&color=&season=&occasion=&needs_review=&page=&per_page=
    响应额外返回 pending_review：当前用户待确认的衣物总数
    Header: Authorization: Bearer <token>
    """
    user_id = _current_user_id()
    page, per_page = _parse_pagination()

    items, total = ItemService.list_items(
        user_id=user_id,
        item_type=request.args.get('type'),
        color=request.args.get('color'),
        season=request.args.get('season'),
        occasion=request.args.get('occasion'),
        needs_review=_parse_review_filter(),
        page=page,
        per_page=per_page,
    )

    return success(data={
        'total': total,
        'page': page,
        'per_page': per_page,
        'list': [item.to_dict() for item in items],
        # 待确认数量（不受筛选条件影响），衣橱页据此提示「有 N 件待确认」
        'pending_review': ItemService.count_pending_review(user_id),
    })


@item_bp.get('/<int:item_id>')
@jwt_required()
def get_item(item_id: int):
    """
    获取单件衣物详情
    GET /api/items/<item_id>
    Header: Authorization: Bearer <token>
    """
    user_id = _current_user_id()
    item = ItemService.get_item(user_id=user_id, item_id=item_id)
    return success(data=item.to_dict())


@item_bp.put('/<int:item_id>')
@jwt_required()
def update_item(item_id: int):
    """
    更新衣物（部分更新）
    PUT /api/items/<item_id>
    Header: Authorization: Bearer <token>
    Body: 支持 image_url, type, color, season, occasion, material, brand, price, purchase_date, status, remark
    """
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}

    item = ItemService.update_item(user_id=user_id, item_id=item_id, data=data)
    return success(data=item.to_dict(), msg='更新成功')


@item_bp.delete('/<int:item_id>')
@jwt_required()
def delete_item(item_id: int):
    """
    软删除衣物
    DELETE /api/items/<item_id>
    Header: Authorization: Bearer <token>
    """
    user_id = _current_user_id()
    ItemService.delete_item(user_id=user_id, item_id=item_id)
    return success(msg='删除成功')
