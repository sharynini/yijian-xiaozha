# -*- coding: utf-8 -*-
"""
穿搭日记业务逻辑层
只处理业务规则，不处理 HTTP 请求/响应
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from app.common.errors import ApiError
from app.extensions import db
from app.models.item import Item
from app.models.outfit import Outfit, OutfitItem
from app.models.wear_log import WearLog, ALLOWED_MOODS


class WearLogService:
    """穿搭日记的增删改查"""

    # ---------------- 创建 ----------------
    @staticmethod
    def create(user_id: int, data: Dict[str, Any]) -> WearLog:
        """
        创建穿搭日记（确认今日穿搭）
        :param data: outfit_id(必填), wear_date?, mood?, content?, photo_url?,
                     temperature?, weather?, increase_wear_count?(默认 false)
        :raises ApiError: 参数错误 / 搭配不存在
        """
        # 1. 校验搭配归属与存在性
        outfit_id = data.get('outfit_id')
        try:
            outfit_id = int(outfit_id)
        except (TypeError, ValueError):
            raise ApiError('outfit_id 不能为空且必须为整数', code=4002)

        outfit = Outfit.query.filter_by(
            id=outfit_id, user_id=user_id, deleted_at=None
        ).first()
        if not outfit:
            raise ApiError('搭配不存在或已被删除', code=4002)

        # 2. 组装衣物快照（当前搭配下未删除的衣物）
        items = WearLogService._load_outfit_items(outfit_id)
        snapshot = [
            {
                'item_id': it.id,
                'image_url': it.image_url,
                'type': it.type,
                'color': it.color,
                'season': it.season,
            }
            for it in items
        ]

        # 3. 组装并校验各字段
        log = WearLog(
            user_id=user_id,
            outfit_id=outfit_id,
            wear_date=WearLogService._parse_wear_date(data.get('wear_date')),
            mood=WearLogService._parse_mood(data.get('mood')),
            content=WearLogService._parse_content(data.get('content')),
            photo_url=(data.get('photo_url') or '').strip() or None,
            temperature=WearLogService._parse_temperature(data.get('temperature')),
            weather=WearLogService._parse_weather(data.get('weather')),
            items_snapshot=snapshot,
        )

        db.session.add(log)

        # 4. 可选：累加对应衣物的穿着次数
        if WearLogService._parse_bool(data.get('increase_wear_count')):
            item_ids = [it.id for it in items]
            if item_ids:
                Item.query.filter(Item.id.in_(item_ids)).update(
                    {'wear_count': Item.wear_count + 1},
                    synchronize_session=False,
                )

        db.session.commit()
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
        """一句话日记：允许为空，最长 500 字"""
        if value is None:
            return None
        content = str(value).strip()
        if not content:
            return None
        if len(content) > 500:
            raise ApiError('一句话日记不能超过 500 字', code=4002)
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
