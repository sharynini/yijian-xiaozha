# -*- coding: utf-8 -*-
"""
穿搭日记业务逻辑层
只处理业务规则，不处理 HTTP 请求/响应
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from app.common.collage import parse_collage
from app.common.errors import ApiError
from app.common.media import to_storage_path
from app.extensions import db
from app.models.item import Item
from app.models.outfit import Outfit, OutfitItem
from app.models.wear_log import WearLog, ALLOWED_MOODS

# 一次确认穿搭允许的衣物件数（去重后）
MIN_ITEM_COUNT = 1
MAX_ITEM_COUNT = 12



class WearLogService:
    """穿搭日记的增删改查"""

    # ---------------- 创建 ----------------
    @staticmethod
    def create(user_id: int, data: Dict[str, Any]) -> WearLog:
        """
        创建穿搭日记（确认今日穿搭）
        :param data: item_ids（1~12 件，与 outfit_id 二选一，优先 item_ids）
                     outfit_id（可选，兼容旧客户端）
                     wear_date?, mood?, content?, photo_url?,
                     temperature?, weather?, increase_wear_count?(默认 false)
        :raises ApiError: 参数错误 / 衣物或搭配无效
        """
        try:
            items, outfit_id = WearLogService._resolve_items(user_id, data)
            snapshot = WearLogService._build_snapshot(items)

            log = WearLog(
                user_id=user_id,
                outfit_id=outfit_id,
                wear_date=WearLogService._parse_wear_date(data.get('wear_date')),
                mood=WearLogService._parse_mood(data.get('mood')),
                content=WearLogService._parse_content(data.get('content')),
                photo_url=to_storage_path((data.get('photo_url') or '').strip() or None),
                temperature=WearLogService._parse_temperature(data.get('temperature')),
                weather=WearLogService._parse_weather(data.get('weather')),
                items_snapshot=snapshot,
                collage=WearLogService._parse_collage(data.get('collage'), [it.id for it in items]),
            )

            db.session.add(log)
            if WearLogService._parse_bool(data.get('increase_wear_count')):
                item_ids = [it.id for it in items]
                if item_ids:
                    Item.query.filter(
                        Item.id.in_(item_ids),
                        Item.user_id == user_id,
                        Item.deleted_at.is_(None),
                    ).update(
                        {'wear_count': Item.wear_count + 1},
                        synchronize_session=False,
                    )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return log

    # ---------------- 时间轴列表 ----------------
    @staticmethod
    def list_logs(user_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[WearLog], int]:
        """
        时间轴：按 wear_date 倒序分页（同日期按创建时间倒序）
        :return: (当前页数据, 总条数)
        """
        query = WearLog.query.filter(
            WearLog.user_id == user_id, WearLog.deleted_at.is_(None)
        ).order_by(WearLog.wear_date.desc(), WearLog.id.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

    # ---------------- 详情 ----------------
    @staticmethod
    def get_log(user_id: int, log_id: int) -> WearLog:
        """
        获取单条日记（仅限本人、未删除）
        :raises ApiError: 日记不存在或无权访问
        """
        log = WearLog.query.filter_by(id=log_id, user_id=user_id, deleted_at=None).first()
        if not log:
            raise ApiError('穿搭日记不存在或已被删除', code=4001, http_status=404)
        return log

    # ---------------- 编辑（仅 mood / content） ----------------
    @staticmethod
    def update_log(user_id: int, log_id: int, data: Dict[str, Any]) -> WearLog:
        """
        编辑日记，仅允许修改 mood 和 content
        :raises ApiError: 日记不存在 / 参数错误
        """
        log = WearLogService.get_log(user_id=user_id, log_id=log_id)

        if 'mood' in data:
            log.mood = WearLogService._parse_mood(data.get('mood'))
        if 'content' in data:
            log.content = WearLogService._parse_content(data.get('content'))

        db.session.commit()
        return log

    # ---------------- 软删除 ----------------
    @staticmethod
    def delete_log(user_id: int, log_id: int) -> None:
        """软删除日记"""
        log = WearLogService.get_log(user_id=user_id, log_id=log_id)
        log.deleted_at = datetime.utcnow()
        db.session.commit()

    # ---------------- 内部：查询与校验 ----------------
    @staticmethod
    def _resolve_items(user_id: int, data: Dict[str, Any]) -> Tuple[List[Item], Optional[int]]:
        """
        解析衣物来源：有 item_ids 走新路径（outfit_id 存 NULL）；
        否则走旧路径，校验 outfit_id 归属。
        """
        if data.get('item_ids') is not None:
            items = WearLogService._load_items_by_ids(user_id, data.get('item_ids'))
            return items, None

        outfit_id = data.get('outfit_id')
        if outfit_id is None or outfit_id == '':
            raise ApiError('item_ids 或 outfit_id 必须提供其一', code=4002)

        try:
            outfit_id = int(outfit_id)
        except (TypeError, ValueError):
            raise ApiError('outfit_id 必须为整数', code=4002)

        outfit = Outfit.query.filter_by(
            id=outfit_id, user_id=user_id, deleted_at=None
        ).first()
        if not outfit:
            raise ApiError('搭配不存在或已被删除', code=4002)

        items = WearLogService._load_outfit_items(outfit_id)
        if not items:
            raise ApiError('搭配下没有可用衣物', code=4002)
        return items, outfit_id

    @staticmethod
    def _load_items_by_ids(user_id: int, item_ids: Any) -> List[Item]:
        """按 item_ids 拉取衣物：去重保序，1~12 件，须全部属于当前用户且未删除。"""
        if not isinstance(item_ids, list):
            raise ApiError('item_ids 必须为数组', code=4002)
        if len(item_ids) == 0:
            raise ApiError('item_ids 不能为空数组', code=4002)

        unique_ids: List[int] = []
        for raw in item_ids:
            try:
                iid = int(raw)
            except (TypeError, ValueError):
                raise ApiError('item_ids 必须为整数数组', code=4002)
            if iid not in unique_ids:
                unique_ids.append(iid)

        if len(unique_ids) < MIN_ITEM_COUNT:
            raise ApiError('item_ids 不能为空数组', code=4002)
        if len(unique_ids) > MAX_ITEM_COUNT:
            raise ApiError(f'一次最多选择 {MAX_ITEM_COUNT} 件衣物', code=4002)

        found = Item.query.filter(Item.id.in_(unique_ids)).all()
        found_map = {it.id: it for it in found}

        others: List[int] = []
        deleted: List[int] = []
        for iid in unique_ids:
            it = found_map.get(iid)
            # 不存在或归属他人一律按「他人衣物」处理，避免泄露他人软删状态
            if it is None or it.user_id != user_id:
                others.append(iid)
            elif it.deleted_at is not None:
                deleted.append(iid)

        if others:
            raise ApiError('存在不属于当前用户的衣物', code=4003)
        if deleted:
            raise ApiError('存在已删除的衣物', code=4004)

        return [found_map[iid] for iid in unique_ids]

    @staticmethod
    def _build_snapshot(items: List[Item]) -> List[Dict[str, Any]]:
        """按传入顺序生成 items_snapshot。"""
        return [
            {
                'item_id': it.id,
                'image_url': to_storage_path(it.image_url),
                'type': it.type,
                'color': it.color,
                'season': it.season,
            }
            for it in items
        ]

    @staticmethod
    def _parse_collage(value: Any, item_ids: List[int]) -> Optional[List[Dict[str, Any]]]:
        """手动搭配画布布局（选填），规则见 app/common/collage.py；结构错误返回 4005"""
        return parse_collage(value, item_ids, error_code=4005)

    @staticmethod
    def _load_outfit_items(outfit_id: int) -> List[Item]:
        """查询搭配下未删除的衣物"""
        return (
            Item.query
            .join(OutfitItem, OutfitItem.item_id == Item.id)
            .filter(OutfitItem.outfit_id == outfit_id, Item.deleted_at.is_(None))
            .order_by(OutfitItem.id.asc())
            .all()
        )

    @staticmethod
    def _parse_wear_date(value: Any) -> date:
        """穿搭日期：缺省为今天，否则须为 YYYY-MM-DD"""
        if value is None or value == '':
            return date.today()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except ValueError:
            raise ApiError('穿搭日期格式不正确，应为 YYYY-MM-DD', code=4002)

    @staticmethod
    def _parse_mood(value: Any) -> Optional[str]:
        """心情：允许为空，否则须在枚举内"""
        if value is None or value == '':
            return None
        mood = str(value).strip()
        if mood not in ALLOWED_MOODS:
            raise ApiError(f'心情不合法，可选：{"、".join(ALLOWED_MOODS)}', code=4002)
        return mood

    @staticmethod
    def _parse_content(value: Any) -> Optional[str]:
        """一句话日记：允许为空，最长 100 字（与前端对齐）"""
        if value is None:
            return None
        content = str(value).strip()
        if not content:
            return None
        if len(content) > 100:
            raise ApiError('一句话日记不能超过 100 字', code=4002)
        return content

    @staticmethod
    def _parse_temperature(value: Any) -> Optional[Decimal]:
        """温度：允许为空，否则为数字"""
        if value is None or value == '':
            return None
        try:
            return Decimal(str(value)).quantize(Decimal('0.1'))
        except (InvalidOperation, ValueError):
            raise ApiError('温度格式不正确', code=4002)

    @staticmethod
    def _parse_weather(value: Any) -> Optional[str]:
        """天气：允许为空，最长 20 字"""
        if value is None:
            return None
        weather = str(value).strip()
        if not weather:
            return None
        if len(weather) > 20:
            raise ApiError('天气描述不能超过 20 字', code=4002)
        return weather

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        """宽松布尔解析：true/1/'true' 视为真"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ('true', '1', 'yes')
        return bool(value)
