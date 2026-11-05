# -*- coding: utf-8 -*-
"""
搭配业务逻辑层
只处理业务规则，不处理 HTTP 请求/响应

约定：
  - 名称选填，不填自动生成「M月D日的搭配」；因此新建的搭配 name 一定不为空。
    name 为 NULL 的是早期日记流程自动建的临时搭配，列表里不展示。
  - collage 为画布布局（可空），规则见 app/common/collage.py
  - 删除为软删除；注销账号时由 AuthService 彻底删除
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.common.collage import parse_collage
from app.common.errors import ApiError
from app.extensions import db
from app.models.item import Item
from app.models.outfit import Outfit, OutfitItem

MAX_ITEM_COUNT = 12
MAX_NAME_LENGTH = 30


class OutfitService:
    """搭配方案的增删改查"""

    # ---------------- 创建 ----------------
    @staticmethod
    def create(user_id: int, item_ids: Any, name: Any = None, collage: Any = None) -> Outfit:
        """
        创建搭配
        :param item_ids: 衣物 ID 数组（1~12 件，必须都属于当前用户且未删除）
        :param name: 选填，空则自动命名
        :param collage: 选填，画布布局
        :raises ApiError: 3001 衣物无效 / 3002 参数错误
        """
        unique_ids = OutfitService._validate_item_ids(user_id, item_ids)

        outfit = Outfit(
            user_id=user_id,
            name=OutfitService._parse_name(name, allow_empty=True) or OutfitService._default_name(),
            collage=parse_collage(collage, unique_ids, error_code=3002),
        )
        db.session.add(outfit)
        db.session.flush()  # 拿到 outfit.id
        for iid in unique_ids:
            db.session.add(OutfitItem(outfit_id=outfit.id, item_id=iid))
        db.session.commit()
        return outfit

    # ---------------- 列表 ----------------
    @staticmethod
    def list_outfits(user_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        """
        我的搭配：只列有名字的（排除早期遗留的临时搭配），最近修改的在前
        :return: (当前页搭配详情列表, 总条数)
        """
        query = Outfit.query.filter(
            Outfit.user_id == user_id,
            Outfit.deleted_at.is_(None),
            Outfit.name.isnot(None),
        ).order_by(Outfit.updated_at.desc(), Outfit.id.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        outfits = pagination.items
        items_by_outfit = OutfitService._load_items_for(outfit.id for outfit in outfits)
        return [OutfitService._serialize(o, items_by_outfit.get(o.id, [])) for o in outfits], pagination.total

    # ---------------- 详情 ----------------
    @staticmethod
    def get_detail(user_id: int, outfit_id: int) -> Dict[str, Any]:
        """
        获取搭配详情（含衣物列表）
        :raises ApiError: 搭配不存在或无权访问
        """
        outfit = OutfitService._get_own(user_id, outfit_id)
        items = OutfitService._load_items_for([outfit_id]).get(outfit_id, [])
        return OutfitService._serialize(outfit, items)

    # ---------------- 更新 ----------------
    @staticmethod
    def update(user_id: int, outfit_id: int, data: Dict[str, Any]) -> Outfit:
        """
        部分更新：出现哪个字段就改哪个
          - name：不能为空
          - item_ids：整体替换搭配内衣物
          - collage：画布布局；只改 item_ids 不传 collage 时，旧布局里已移除的衣物会被去掉
        :raises ApiError: 3001 搭配或衣物无效 / 3002 参数错误
        """
        outfit = OutfitService._get_own(user_id, outfit_id)

        if 'name' in data:
            outfit.name = OutfitService._parse_name(data.get('name'), allow_empty=False)

        if 'item_ids' in data:
            new_ids = OutfitService._validate_item_ids(user_id, data.get('item_ids'))
            OutfitItem.query.filter_by(outfit_id=outfit.id).delete(synchronize_session=False)
            for iid in new_ids:
                db.session.add(OutfitItem(outfit_id=outfit.id, item_id=iid))
            current_ids = new_ids
        else:
            current_ids = [row.item_id for row in OutfitItem.query.filter_by(outfit_id=outfit.id)]

        if 'collage' in data:
            outfit.collage = parse_collage(data.get('collage'), current_ids, error_code=3002)
        elif 'item_ids' in data and outfit.collage:
            kept = [entry for entry in outfit.collage if entry.get('item_id') in set(current_ids)]
            outfit.collage = kept or None

        outfit.updated_at = datetime.utcnow()  # 只改关联表时 onupdate 不会触发，手动刷新排序时间
        db.session.commit()
        return outfit

    # ---------------- 删除 ----------------
    @staticmethod
    def delete(user_id: int, outfit_id: int) -> None:
        """软删除；已经用这套记录过的日记有自己的衣物快照，不受影响"""
        outfit = OutfitService._get_own(user_id, outfit_id)
        outfit.deleted_at = datetime.utcnow()
        db.session.commit()

    # ---------------- 内部 ----------------
    @staticmethod
    def _get_own(user_id: int, outfit_id: int) -> Outfit:
        outfit = Outfit.query.filter_by(id=outfit_id, user_id=user_id, deleted_at=None).first()
        if not outfit:
            raise ApiError('搭配不存在或已被删除', code=3001, http_status=404)
        return outfit

    @staticmethod
    def _validate_item_ids(user_id: int, item_ids: Any) -> List[int]:
        """去重保序，校验 1~12 件且都属于当前用户、未删除"""
        if not isinstance(item_ids, list) or not item_ids:
            raise ApiError('item_ids 必须为非空数组', code=3002)

        unique_ids: List[int] = []
        for raw in item_ids:
            if isinstance(raw, bool):
                raise ApiError('item_ids 必须为整数数组', code=3002)
            try:
                iid = int(raw)
            except (TypeError, ValueError):
                raise ApiError('item_ids 必须为整数数组', code=3002)
            if iid not in unique_ids:
                unique_ids.append(iid)
        if len(unique_ids) > MAX_ITEM_COUNT:
            raise ApiError(f'一套搭配最多 {MAX_ITEM_COUNT} 件衣物', code=3002)

        count = Item.query.filter(
            Item.id.in_(unique_ids),
            Item.user_id == user_id,
            Item.deleted_at.is_(None),
        ).count()
        if count != len(unique_ids):
            raise ApiError('存在无效的衣物，无法保存搭配', code=3001)
        return unique_ids

    @staticmethod
    def _parse_name(value: Any, allow_empty: bool) -> Optional[str]:
        name = str(value).strip() if value is not None else ''
        if not name:
            if allow_empty:
                return None
            raise ApiError('搭配名称不能为空', code=3002)
        if len(name) > MAX_NAME_LENGTH:
            raise ApiError(f'搭配名称不能超过 {MAX_NAME_LENGTH} 个字', code=3002)
        return name

    @staticmethod
    def _default_name() -> str:
        today = date.today()
        return f'{today.month}月{today.day}日的搭配'

    @staticmethod
    def _load_items_for(outfit_ids) -> Dict[int, List[Item]]:
        """批量查询若干搭配下未删除的衣物，按加入顺序；返回 {outfit_id: [Item]}"""
        ids = list(outfit_ids)
        if not ids:
            return {}
        rows = (
            db.session.query(OutfitItem.outfit_id, Item)
            .join(Item, OutfitItem.item_id == Item.id)
            .filter(OutfitItem.outfit_id.in_(ids), Item.deleted_at.is_(None))
            .order_by(OutfitItem.id.asc())
            .all()
        )
        result: Dict[int, List[Item]] = {}
        for outfit_id, item in rows:
            result.setdefault(outfit_id, []).append(item)
        return result

    @staticmethod
    def _serialize(outfit: Outfit, items: List[Item]) -> Dict[str, Any]:
        """搭配 + 衣物；衣物被删除后，布局里对应的项也一并去掉"""
        alive = {item.id for item in items}
        data = outfit.to_dict()
        data['collage'] = [e for e in (outfit.collage or []) if e.get('item_id') in alive] or None
        data['items'] = [item.to_dict() for item in items]
        data['item_count'] = len(items)
        data['updated_at'] = outfit.updated_at.strftime('%Y-%m-%d %H:%M:%S') if outfit.updated_at else None
        return data
