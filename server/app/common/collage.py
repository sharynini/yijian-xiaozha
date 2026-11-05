# -*- coding: utf-8 -*-
"""
手动搭配画布布局（collage）的校验，穿搭日记与搭配方案共用

格式：[{ item_id, x, y, w, z }]
  - item_id：必须在本次选择的衣物内
  - x / y：左上角，相对画布边长 0~1
  - w：宽度占画布边长比例 0.05~1
  - z：层级 0~99
数值越界会被夹到合法范围；结构不对直接报错。
"""
from typing import Any, Dict, Iterable, List, Optional

from app.common.errors import ApiError

MAX_COLLAGE_ITEMS = 12
COLLAGE_MIN_W = 0.05
COLLAGE_MAX_W = 1.0


def parse_collage(value: Any, item_ids: Iterable[int], error_code: int) -> Optional[List[Dict[str, Any]]]:
    """
    :param value: 前端传来的 collage；None / [] 视为不保存布局
    :param item_ids: 本次允许出现的衣物 ID
    :param error_code: 结构错误时抛出的业务码（日记 4005，搭配 3002）
    """
    if value is None or value == []:
        return None
    if not isinstance(value, list) or len(value) > MAX_COLLAGE_ITEMS:
        raise ApiError(f'collage 须为最多 {MAX_COLLAGE_ITEMS} 项的数组', code=error_code)

    allowed = set(item_ids)
    result = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ApiError('collage 每一项须为对象', code=error_code)
        try:
            item_id = int(entry.get('item_id'))
            x = float(entry.get('x', 0))
            y = float(entry.get('y', 0))
            w = float(entry.get('w', 0.3))
            z = int(entry.get('z', 0))
        except (TypeError, ValueError):
            raise ApiError('collage 坐标须为数字', code=error_code)
        if item_id not in allowed:
            raise ApiError('collage 里包含未选择的衣物', code=error_code)

        result.append({
            'item_id': item_id,
            'x': round(min(max(x, 0.0), 1.0), 4),
            'y': round(min(max(y, 0.0), 1.0), 4),
            'w': round(min(max(w, COLLAGE_MIN_W), COLLAGE_MAX_W), 4),
            'z': min(max(z, 0), 99),
        })
    return result
