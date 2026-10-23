# -*- coding: utf-8 -*-
"""
搭配业务逻辑层
只处理业务规则，不处理 HTTP 请求/响应
"""
from typing import Any, Dict, List, Optional

from app.common.errors import ApiError
from app.extensions import db
from app.models.item import Item
from app.models.outfit import Outfit, OutfitItem


class OutfitService:
    """搭配方案的创建与查询"""

    # ---------------- 创建 ----------------
    @staticmethod
    def create(user_id: int, item_ids: Any, name: Optional[str] = None) -> Outfit:
        """
        创建搭配
        :param item_ids: 衣物 ID 数组（至少 1 件，且必须都属于当前用户且未删除）
        :raises ApiError: 参数错误 / 衣物不存在
        """
        # 1. 基础校验
        if not isinstance(item_ids, list) or not item_ids:
            raise ApiError('item_ids 必须为非空数组', code=3002)

        # 去重并保持顺序
        unique_ids: List[int] = []
        for raw in item_ids:
            try:
                iid = int(raw)
            except (TypeError, ValueError):
                raise ApiError('item_ids 必须为整数数组', code=3002)
            if iid not in unique_ids:
                unique_ids.append(iid)

        # 2. 校验衣物归属与存在性（防止操作他人数据）
        items = Item.query.filter(
            Item.id.in_(unique_ids),
            Item.user_id == user_id,
            Item.deleted_at.is_(None),
        ).all()
        if len(items) != len(unique_ids):
            raise ApiError('存在无效的衣物，无法创建搭配', code=3001)

        # 3. 创建搭配方案
        outfit = Outfit(user_id=user_id, name=(name or '').strip() or None)
        db.session.add(outfit)
        db.session.flush()  # 拿到 outfit.id

        for iid in unique_ids:
            db.session.add(OutfitItem(outfit_id=outfit.id, item_id=iid))

        db.session.commit()
        return outfit

    # ---------------- 详情 ----------------
    @staticmethod
    def get_detail(user_id: int, outfit_id: int) -> Dict[str, Any]:
        """
        获取搭配详情（含衣物列表）
        :raises ApiError: 搭配不存在或无权访问
        """
        outfit = Outfit.query.filter_by(
            id=outfit_id, user_id=user_id, deleted_at=None
        ).first()
        if not outfit:
            raise ApiError('搭配不存在或已被删除', code=3001, http_status=404)

        items = OutfitService._load_items(outfit_id)

        data = outfit.to_dict()
        data['items'] = [item.to_dict() for item in items]
        data['item_count'] = len(items)
        return data

    # ---------------- 内部 ----------------
    @staticmethod
    def _load_items(outfit_id: int) -> List[Item]:
        """查询某搭配下、未被软删除的衣物列表"""
        return (
            Item.query
            .join(OutfitItem, OutfitItem.item_id == Item.id)
            .filter(OutfitItem.outfit_id == outfit_id, Item.deleted_at.is_(None))
            .order_by(OutfitItem.id.asc())
            .all()
        )
