# -*- coding: utf-8 -*-
"""
衣物业务逻辑层
只处理业务规则，不处理 HTTP 请求/响应
"""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from app.common.errors import ApiError
from app.common.media import to_storage_path
from app.extensions import db
from app.models.item import Item, UNCLASSIFIED_TYPE
from app.models.outfit import Outfit, OutfitItem

# 允许的字段取值（与 schema.sql 注释保持一致）
ALLOWED_TYPES = {'上装', '下装', '连衣裙', '外套', '鞋子', '包包', '帽子', '配饰'}
ALLOWED_SEASONS = {'春', '夏', '秋', '冬', '全季'}
ALLOWED_OCCASIONS = {'日常', '工作', '运动', '正式'}
ALLOWED_STATUS = {'正常', '洗衣中', '收纳中'}

# 批量操作一次最多处理的衣物数
BATCH_MAX_IDS = 100
# 删除后可撤销的时间窗口：超过这个时间的删除不能再通过「撤销」恢复
RESTORE_WINDOW = timedelta(minutes=10)

# 可写入的字段白名单
EDITABLE_FIELDS = (
    'image_url', 'type', 'color', 'season', 'occasion',
    'material', 'brand', 'price', 'purchase_date', 'status', 'remark', 'needs_review',
)


class ItemService:
    """衣物的增删改查"""

    # ---------------- 新增 ----------------
    @staticmethod
    def create(user_id: int, data: Dict[str, Any]) -> Item:
        """
        添加衣物
        :raises ApiError: 参数错误
        """
        ItemService._validate_required(data)

        item = Item(user_id=user_id)
        ItemService._apply_fields(item, data, is_create=True)
        if not item.season:
            item.season = '全季'

        db.session.add(item)
        db.session.commit()
        return item

    # ---------------- 列表（筛选 + 分页） ----------------
    @staticmethod
    def list_items(
        user_id: int,
        item_type: Optional[str] = None,
        color: Optional[str] = None,
        season: Optional[str] = None,
        occasion: Optional[str] = None,
        needs_review: Optional[bool] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Item], int]:
        """
        查询当前用户的衣物列表（自动排除软删除）
        :return: (当前页数据, 总条数)
        """
        query = Item.query.filter(Item.user_id == user_id, Item.deleted_at.is_(None))

        # 多条件筛选（等值匹配，条件之间为 AND）
        if item_type:
            query = query.filter(Item.type == item_type)
        if color:
            query = query.filter(Item.color == color)
        if season:
            query = query.filter(Item.season == season)
        if occasion:
            query = query.filter(Item.occasion == occasion)
        if needs_review is not None:
            query = query.filter(Item.needs_review.is_(needs_review))

        query = query.order_by(Item.created_at.desc(), Item.id.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

    @staticmethod
    def count_pending_review(user_id: int) -> int:
        """当前用户待确认（批量上传后尚未核对）的衣物数量"""
        return Item.query.filter(
            Item.user_id == user_id,
            Item.deleted_at.is_(None),
            Item.needs_review.is_(True),
        ).count()

    # ---------------- 详情 ----------------
    @staticmethod
    def get_item(user_id: int, item_id: int) -> Item:
        """
        获取单件衣物（仅限本人、未删除）
        :raises ApiError: 衣物不存在或无权访问
        """
        item = Item.query.filter_by(id=item_id, user_id=user_id, deleted_at=None).first()
        if not item:
            raise ApiError('衣物不存在或已被删除', code=2001, http_status=404)
        return item

    # ---------------- 更新 ----------------
    @staticmethod
    def update_item(user_id: int, item_id: int, data: Dict[str, Any]) -> Item:
        """
        更新衣物（部分更新，只处理请求中出现的字段）
        :raises ApiError: 衣物不存在 / 参数错误
        """
        item = ItemService.get_item(user_id, item_id)

        # 若显式传入 type，则不允许为空
        if 'type' in data:
            ItemService._validate_required({**data, 'image_url': data.get('image_url', item.image_url)})

        ItemService._apply_fields(item, data, is_create=False)

        db.session.commit()
        return item

    # ---------------- 软删除 ----------------
    @staticmethod
    def delete_item(user_id: int, item_id: int) -> None:
        """
        软删除衣物（置 deleted_at，列表不再返回；历史记录按快照保留）
        :raises ApiError: 衣物不存在或无权访问
        """
        item = ItemService.get_item(user_id, item_id)
        item.deleted_at = datetime.utcnow()
        db.session.commit()

    # ---------------- 批量操作 ----------------
    @staticmethod
    def parse_ids(raw: Any) -> List[int]:
        """
        校验批量操作的 ids：必须是非空列表、元素为正整数、不超过 BATCH_MAX_IDS；去重并保持顺序
        :raises ApiError: 2002 参数错误
        """
        if not isinstance(raw, list) or not raw:
            raise ApiError('请至少选择一件衣物', code=2002)
        ids: List[int] = []
        for v in raw:
            # bool 是 int 的子类，单独排除
            if isinstance(v, bool) or not isinstance(v, (int, str)):
                raise ApiError('衣物 ID 不合法', code=2002)
            try:
                n = int(v)
            except ValueError:
                raise ApiError('衣物 ID 不合法', code=2002)
            if n <= 0:
                raise ApiError('衣物 ID 不合法', code=2002)
            if n not in ids:
                ids.append(n)
        if len(ids) > BATCH_MAX_IDS:
            raise ApiError(f'一次最多操作 {BATCH_MAX_IDS} 件衣物', code=2002)
        return ids

    @staticmethod
    def batch_delete(user_id: int, ids: List[int]) -> List[int]:
        """
        批量软删除：只删本人、未删除的衣物；别人的或已删除的 ID 直接忽略
        一个事务内完成，要么全部删除，要么都不删
        :return: 实际删除的衣物 ID（前端用于「撤销」）
        """
        items = Item.query.filter(
            Item.user_id == user_id, Item.id.in_(ids), Item.deleted_at.is_(None)
        ).all()
        now = datetime.utcnow()
        for item in items:
            item.deleted_at = now
        db.session.commit()
        return [item.id for item in items]

    @staticmethod
    def restore(user_id: int, ids: List[int]) -> List[int]:
        """
        撤销删除：只恢复本人在 RESTORE_WINDOW 内删除的衣物
        :return: 实际恢复的衣物 ID
        """
        since = datetime.utcnow() - RESTORE_WINDOW
        items = Item.query.filter(
            Item.user_id == user_id, Item.id.in_(ids),
            Item.deleted_at.isnot(None), Item.deleted_at >= since,
        ).all()
        for item in items:
            item.deleted_at = None
        db.session.commit()
        return [item.id for item in items]

    @staticmethod
    def delete_impact(user_id: int, ids: List[int]) -> Dict[str, int]:
        """
        删除前的影响预估：选中的衣物出现在多少套（本人、未删除的）搭配里
        :return: { items_in_outfits: 涉及的衣物件数, outfits: 受影响的搭配套数 }
        """
        rows = (
            db.session.query(OutfitItem.item_id, OutfitItem.outfit_id)
            .join(Outfit, Outfit.id == OutfitItem.outfit_id)
            .join(Item, Item.id == OutfitItem.item_id)
            .filter(
                OutfitItem.item_id.in_(ids),
                Item.user_id == user_id, Item.deleted_at.is_(None),
                Outfit.user_id == user_id, Outfit.deleted_at.is_(None),
            )
            .all()
        )
        return {
            'items_in_outfits': len({r.item_id for r in rows}),
            'outfits': len({r.outfit_id for r in rows}),
        }

    @staticmethod
    def batch_confirm(user_id: int, ids: List[int]) -> Dict[str, Any]:
        """
        批量确认待确认的衣物（needs_review → false）
        「未分类」的必须先选类别，跳过并返回数量；不是本人 / 已删除 / 本来就已确认的忽略
        """
        items = Item.query.filter(
            Item.user_id == user_id, Item.id.in_(ids),
            Item.deleted_at.is_(None), Item.needs_review.is_(True),
        ).all()
        confirmed, skipped = [], []
        for item in items:
            if item.type == UNCLASSIFIED_TYPE:
                skipped.append(item.id)
            else:
                item.needs_review = False
                confirmed.append(item.id)
        db.session.commit()
        return {'confirmed': confirmed, 'skipped_unclassified': skipped}

    # ---------------- 内部：字段校验与赋值 ----------------
    @staticmethod
    def _validate_required(data: Dict[str, Any]) -> None:
        """新增时的必填校验"""
        image_url = (data.get('image_url') or '').strip()
        if not image_url:
            raise ApiError('衣物图片不能为空', code=2002)

        item_type = (data.get('type') or '').strip()
        if not item_type:
            raise ApiError('衣物类型不能为空', code=2002)
        if item_type not in ALLOWED_TYPES and item_type != UNCLASSIFIED_TYPE:
            raise ApiError(f'衣物类型不合法，可选：{"、".join(ALLOWED_TYPES)}', code=2002)

    @staticmethod
    def _apply_fields(item: Item, data: Dict[str, Any], is_create: bool) -> None:
        """
        将请求数据写入模型实例，并做取值校验
        :param is_create: 新增时对未提供的字段使用默认值
        """
        # 先算出写入后的「类别 + 待确认」组合并校验，避免改了一半才报错：
        # 「未分类」只允许出现在待确认的衣物上，确认（needs_review=false）前必须先选好真实类别
        target_review = (ItemService._parse_bool(data['needs_review']) if 'needs_review' in data
                         else bool(item.needs_review))
        target_type = (data.get('type') or '').strip() if 'type' in data else item.type
        if target_type == UNCLASSIFIED_TYPE and not target_review:
            raise ApiError('还没有选择衣物类别，请先选好类别再确认', code=2003)

        for field in EDITABLE_FIELDS:
            if field not in data:
                continue  # 部分更新：未出现的字段保持原值

            value = data[field]

            if field == 'image_url':
                value = (value or '').strip()
                if not value:
                    raise ApiError('衣物图片不能为空', code=2002)
                # 本站图片只存相对路径，换域名后不失效
                item.image_url = to_storage_path(value)

            elif field == 'type':
                value = (value or '').strip()
                if value not in ALLOWED_TYPES and value != UNCLASSIFIED_TYPE:
                    raise ApiError(f'衣物类型不合法，可选：{"、".join(ALLOWED_TYPES)}', code=2002)
                item.type = value

            elif field == 'needs_review':
                item.needs_review = target_review

            elif field == 'season':
                value = (value or '').strip() or None
                if is_create and not value:
                    value = '全季'
                if value is not None and value not in ALLOWED_SEASONS:
                    raise ApiError(f'季节不合法，可选：{"、".join(ALLOWED_SEASONS)}', code=2002)
                item.season = value

            elif field == 'occasion':
                value = (value or '').strip() or None
                if value is not None and value not in ALLOWED_OCCASIONS:
                    raise ApiError(f'场合不合法，可选：{"、".join(ALLOWED_OCCASIONS)}', code=2002)
                item.occasion = value

            elif field == 'status':
                value = (value or '').strip()
                if value not in ALLOWED_STATUS:
                    raise ApiError(f'状态不合法，可选：{"、".join(ALLOWED_STATUS)}', code=2002)
                item.status = value

            elif field == 'price':
                item.price = ItemService._parse_price(value)

            elif field == 'purchase_date':
                item.purchase_date = ItemService._parse_date(value)

            else:
                # color / material / brand / remark：纯文本，空串统一存 None
                value = (value or '').strip() or None
                setattr(item, field, value)

        # 新增时填充默认值
        if is_create:
            if not item.status:
                item.status = '正常'
            if item.wear_count is None:
                item.wear_count = 0
            if item.needs_review is None:
                item.needs_review = False

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        """解析布尔参数：支持 true/false、1/0 及其字符串形式"""
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in ('true', '1', 'false', '0'):
            return value.strip().lower() in ('true', '1')
        raise ApiError('needs_review 只能是 true 或 false', code=2002)

    @staticmethod
    def _parse_price(value: Any) -> Optional[Decimal]:
        """价格校验：允许为空，否则须为非负数字"""
        if value is None or value == '':
            return None
        try:
            price = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ApiError('价格格式不正确', code=2002)
        if price < 0:
            raise ApiError('价格不能为负数', code=2002)
        return price.quantize(Decimal('0.01'))

    @staticmethod
    def _parse_date(value: Any) -> Optional[Any]:
        """购买日期校验：允许为空，否则须为 YYYY-MM-DD"""
        if value is None or value == '':
            return None
        if isinstance(value, datetime):
            return value.date()
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except ValueError:
            raise ApiError('购买日期格式不正确，应为 YYYY-MM-DD', code=2002)
