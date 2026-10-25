# -*- coding: utf-8 -*-
"""
衣物业务逻辑层
只处理业务规则，不处理 HTTP 请求/响应
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from app.common.errors import ApiError
from app.common.media import to_storage_path
from app.extensions import db
from app.models.item import Item

# 允许的字段取值（与 schema.sql 注释保持一致）
ALLOWED_TYPES = {'上装', '下装', '外套', '鞋子', '配饰'}
ALLOWED_SEASONS = {'春', '夏', '秋', '冬', '全季'}
ALLOWED_OCCASIONS = {'日常', '工作', '运动', '正式'}
ALLOWED_STATUS = {'正常', '洗衣中', '收纳中'}

# 可写入的字段白名单
EDITABLE_FIELDS = (
    'image_url', 'type', 'color', 'season', 'occasion',
    'material', 'brand', 'price', 'purchase_date', 'status', 'remark',
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

        query = query.order_by(Item.created_at.desc(), Item.id.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

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
        if item_type not in ALLOWED_TYPES:
            raise ApiError(f'衣物类型不合法，可选：{"、".join(ALLOWED_TYPES)}', code=2002)

    @staticmethod
    def _apply_fields(item: Item, data: Dict[str, Any], is_create: bool) -> None:
        """
        将请求数据写入模型实例，并做取值校验
        :param is_create: 新增时对未提供的字段使用默认值
        """
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
                if value not in ALLOWED_TYPES:
                    raise ApiError(f'衣物类型不合法，可选：{"、".join(ALLOWED_TYPES)}', code=2002)
                item.type = value

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
