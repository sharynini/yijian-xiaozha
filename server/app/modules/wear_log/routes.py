# -*- coding: utf-8 -*-
"""
穿搭日记路由层
只负责接收请求、调用服务、返回响应
所有接口均需 JWT 鉴权，只能操作当前登录用户自己的数据
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.common.response import success
from app.modules.wear_log.services import WearLogService

wear_log_bp = Blueprint('wear_log', __name__)

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 50


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _parse_pagination() -> tuple:
    """解析并校验分页参数（非法值回退默认）"""
    try:
        page = int(request.args.get('page', DEFAULT_PAGE))
    except (TypeError, ValueError):
        page = DEFAULT_PAGE
    try:
        per_page = int(request.args.get('per_page', DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    return max(page, 1), min(max(per_page, 1), MAX_PER_PAGE)


@wear_log_bp.post('')
@jwt_required()
def create_log():
    """
    创建穿搭日记（确认今日穿搭）
    POST /api/wear-logs
    Header: Authorization: Bearer <token>
    Body: {
        "item_ids": [1, 2, 3],              # 与 outfit_id 二选一；1~12 件，去重；优先于 outfit_id
        "outfit_id": 1,                     # 选填，兼容旧客户端（未传 item_ids 时沿用旧逻辑）
        "wear_date": "2026-10-19",          # 选填，缺省今天
        "mood": "开心",                      # 选填
        "content": "今天天气很好",            # 选填
        "photo_url": "https://...",          # 选填
        "temperature": 25.5,                 # 选填
        "weather": "晴",                     # 选填
        "increase_wear_count": true          # 选填，是否累加衣物穿着次数，默认 false
    }
    """
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}

    log = WearLogService.create(user_id=user_id, data=data)
    return success(data=log.to_dict(), msg='记录成功')


@wear_log_bp.get('')
@jwt_required()
def list_logs():
    """
    穿搭时间轴（按 wear_date 倒序分页）
    GET /api/wear-logs?page=&per_page=&date=
    Header: Authorization: Bearer <token>
    date 选填（YYYY-MM-DD）：只返回这一天的记录
    """
    user_id = _current_user_id()
    page, per_page = _parse_pagination()

    logs, total = WearLogService.list_logs(user_id=user_id, page=page, per_page=per_page,
                                           on_date=request.args.get('date'))

    return success(data={
        'total': total,
        'page': page,
        'per_page': per_page,
        'list': [log.to_dict() for log in logs],
    })


@wear_log_bp.get('/<int:log_id>')
@jwt_required()
def get_log(log_id: int):
    """
    获取单条日记详情
    GET /api/wear-logs/<log_id>
    Header: Authorization: Bearer <token>
    """
    user_id = _current_user_id()
    log = WearLogService.get_log(user_id=user_id, log_id=log_id)
    return success(data=log.to_dict())


@wear_log_bp.put('/<int:log_id>')
@jwt_required()
def update_log(log_id: int):
    """
    编辑日记（仅允许修改 mood 和 content）
    PUT /api/wear-logs/<log_id>
    Header: Authorization: Bearer <token>
    Body: { "mood": "平静", "content": "..." }
    """
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}

    log = WearLogService.update_log(user_id=user_id, log_id=log_id, data=data)
    return success(data=log.to_dict(), msg='更新成功')


@wear_log_bp.delete('/<int:log_id>')
@jwt_required()
def delete_log(log_id: int):
    """
    软删除日记
    DELETE /api/wear-logs/<log_id>
    Header: Authorization: Bearer <token>
    """
    user_id = _current_user_id()
    WearLogService.delete_log(user_id=user_id, log_id=log_id)
    return success(msg='删除成功')
