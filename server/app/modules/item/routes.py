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


# ---------------- 批量操作（衣橱多选） ----------------
# 用 POST + JSON body：小程序的 DELETE 请求带 body 兼容性不好，且 ids 可能较多

def _batch_ids():
    data = request.get_json(silent=True) or {}
    return ItemService.parse_ids(data.get('ids'))


@item_bp.post('/batch-delete')
@jwt_required()
def batch_delete_items():
    """
    批量软删除
    POST /api/items/batch-delete   Body: { ids: [1, 2, ...] }（最多 100 个）
    响应 data: { deleted: [实际删除的 ID] }；别人的或已删除的 ID 会被忽略
    """
    deleted = ItemService.batch_delete(_current_user_id(), _batch_ids())
    return success(data={'deleted': deleted}, msg=f'已删除 {len(deleted)} 件')


@item_bp.post('/restore')
@jwt_required()
def restore_items():
    """
    撤销删除（只能恢复 10 分钟内删除的）
    POST /api/items/restore   Body: { ids: [...] }
    响应 data: { restored: [实际恢复的 ID] }
    """
    restored = ItemService.restore(_current_user_id(), _batch_ids())
    return success(data={'restored': restored}, msg=f'已恢复 {len(restored)} 件')


@item_bp.post('/delete-impact')
@jwt_required()
def delete_impact():
    """
    删除前预估影响：选中的衣物在几套已保存的搭配里
    POST /api/items/delete-impact   Body: { ids: [...] }
    响应 data: { items_in_outfits, outfits }
    """
    return success(data=ItemService.delete_impact(_current_user_id(), _batch_ids()))


@item_bp.post('/batch-confirm')
@jwt_required()
def batch_confirm_items():
    """
    批量确认待确认的衣物
    POST /api/items/batch-confirm   Body: { ids: [...] }
    响应 data: { confirmed: [...], skipped_unclassified: [...] }（「未分类」需先选类别，会被跳过）
    """
    result = ItemService.batch_confirm(_current_user_id(), _batch_ids())
    return success(data=result, msg=f'已确认 {len(result["confirmed"])} 件')
