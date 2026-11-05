# -*- coding: utf-8 -*-
"""
今日推荐路由层
只负责接收请求、调用服务、返回响应
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.common.response import success
from app.modules.recommend.services import RecommendService

recommend_bp = Blueprint('recommend', __name__)


@recommend_bp.get('')
@jwt_required()
def recommend():
    """
    基于规则的今日穿搭推荐
    GET /api/recommend?temperature=15&occasion=工作
    Header: Authorization: Bearer <token>
    occasion 选填：日常 / 工作 / 运动 / 正式；不传表示不限
    返回：{ temperature, seasons, season_label, occasion, recent_days, total_candidates, count,
           list: [{items, reason}] }
    count 表示实际可生成的套数（最多 3 套，不足则返回实际套数）
    """
    user_id = int(get_jwt_identity())

    data = RecommendService.recommend(
        user_id=user_id,
        temperature=request.args.get('temperature'),
        occasion=request.args.get('occasion'),
    )
    return success(data=data)
