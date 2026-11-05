# -*- coding: utf-8 -*-
"""
今日穿搭推荐业务逻辑层（基于规则，无 AI / 无外部依赖）

规则：
  1. 依据温度映射季节：<10℃ 冬；10~25℃ 春秋；>=25℃ 夏（"全季"衣物始终参与）
  2. 仅使用当前用户、未软删除、状态为"正常"的对应季节衣物
  3. 可选场合：只用该场合的衣物；没填场合的衣物在任何场合都参与
  4. 组合模板：「上装 + 下装」或「连衣裙」单穿；有外套则附加一件外套，有鞋子则附加一双鞋
  5. 单品排序：近 RECENT_DAYS 天穿过的排在后面（降权，不排除），其次穿着次数少的优先
     → 有别的选择时会避开近期穿过的；实在没有时仍会推荐，理由里会说明
  6. 最多生成 3 套互不重复的搭配，不足则返回实际套数
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set

from app.common.errors import ApiError
from app.extensions import db
from app.models.item import Item
from app.models.wear_log import WearLog
from app.modules.item.services import ALLOWED_OCCASIONS

MAX_OUTFITS = 3
ALL_SEASON = '全季'
RECENT_DAYS = 7


class RecommendService:
    """基于规则的今日推荐"""

    # ---------------- 入口 ----------------
    @staticmethod
    def recommend(user_id: int, temperature: Any, occasion: Any = None) -> Dict[str, Any]:
        """
        生成今日推荐
        :param temperature: 当前温度（数字）
        :param occasion: 场合（选填，日常/工作/运动/正式）
        :return: { temperature, seasons, season_label, occasion, recent_days, total_candidates, count, list }
        :raises ApiError: 5002 参数错误
        """
        temp = RecommendService._parse_temperature(temperature)
        occ = RecommendService._parse_occasion(occasion)
        seasons, season_label, band_word = RecommendService._season_band(temp)

        # 1. 拉取候选衣物（对应季节 + 全季；指定场合时含未填场合的衣物）
        query = Item.query.filter(
            Item.user_id == user_id,
            Item.deleted_at.is_(None),
            Item.status == '正常',
            Item.season.in_(seasons + [ALL_SEASON]),
        )
        if occ:
            query = query.filter(db.or_(Item.occasion == occ, Item.occasion.is_(None)))
        candidates = query.all()

        # 2. 排序：近期没穿过的在前，其次穿着次数少的在前
        recent_ids = RecommendService._recent_item_ids(user_id)
        candidates.sort(key=lambda it: (it.id in recent_ids, it.wear_count or 0, it.id))

        by_type: Dict[str, List[Item]] = {}
        for it in candidates:
            by_type.setdefault(it.type, []).append(it)

        # 3. 生成搭配
        combos = RecommendService._build_combos(
            by_type.get('上装', []), by_type.get('下装', []), by_type.get('外套', []),
            by_type.get('连衣裙', []), by_type.get('鞋子', []),
        )

        result = [
            {
                'items': [it.to_dict() for it in combo['items']],
                'reason': RecommendService._build_reason(temp, season_label, band_word, occ, combo, recent_ids),
            }
            for combo in combos
        ]

        return {
            'temperature': temp,
            'seasons': seasons,
            'season_label': season_label,
            'occasion': occ,
            'recent_days': RECENT_DAYS,
            'total_candidates': len(candidates),
            'count': len(result),
            'list': result,
        }

    # ---------------- 近期穿过 ----------------
    @staticmethod
    def _recent_item_ids(user_id: int) -> Set[int]:
        """近 RECENT_DAYS 天（含今天）日记快照里出现过的衣物 ID"""
        since = date.today() - timedelta(days=RECENT_DAYS - 1)
        logs = WearLog.query.with_entities(WearLog.items_snapshot).filter(
            WearLog.user_id == user_id,
            WearLog.deleted_at.is_(None),
            WearLog.wear_date >= since,
        ).all()
        ids: Set[int] = set()
        for (snapshot,) in logs:
            for entry in snapshot or []:
                if isinstance(entry, dict) and entry.get('item_id') is not None:
                    try:
                        ids.add(int(entry['item_id']))
                    except (TypeError, ValueError):
                        continue
        return ids

    # ---------------- 组合生成 ----------------
    @staticmethod
    def _build_combos(
        tops: List[Item], bottoms: List[Item], outers: List[Item],
        dresses: Optional[List[Item]] = None, shoes: Optional[List[Item]] = None,
    ) -> List[Dict[str, Any]]:
        """
        生成最多 MAX_OUTFITS 套互不重复的搭配
        规则：基础单元为「上装 + 下装」或「连衣裙」；有外套、鞋子则各附一件（轮流取用）
        两类基础单元交替取用，保证有连衣裙时推荐里能看到它；各列表已按优先级排好
        """
        dresses = dresses or []
        shoes = shoes or []
        pairs = [[top, bottom] for top in tops for bottom in bottoms]
        singles = [[dress] for dress in dresses]

        # 交替合并：上下装、连衣裙、上下装、连衣裙……
        bases: List[List[Item]] = []
        for i in range(max(len(pairs), len(singles))):
            if i < len(pairs):
                bases.append(pairs[i])
            if i < len(singles):
                bases.append(singles[i])

        combos: List[Dict[str, Any]] = []
        seen = set()
        extra_idx = 0

        for base in bases:
            outer = outers[extra_idx % len(outers)] if outers else None
            shoe = shoes[extra_idx % len(shoes)] if shoes else None
            extra_idx += 1

            items = base + ([outer] if outer else []) + ([shoe] if shoe else [])
            key = frozenset(it.id for it in items)
            if key in seen:
                continue
            seen.add(key)
            combos.append({'items': items})

            if len(combos) >= MAX_OUTFITS:
                break

        return combos

    # ---------------- 推荐理由 ----------------
    @staticmethod
    def _build_reason(temp: float, season_label: str, band_word: str, occasion: Optional[str],
                      combo: Dict[str, Any], recent_ids: Set[int]) -> str:
        """拼接可解释的推荐理由"""
        items = combo['items']
        types = '、'.join(it.type for it in items)
        extras = []
        if any(it.type == '外套' for it in items):
            extras.append('外套')
        if any(it.type == '鞋子' for it in items):
            extras.append('鞋子')
        extra_note = f"，配了{'和'.join(extras)}" if extras else ''
        occasion_note = f'{occasion}场合的' if occasion else ''

        if any(it.id in recent_ids for it in items):
            recent_note = f'有单品近 {RECENT_DAYS} 天穿过，衣橱里暂时没有更合适的替换'
        elif recent_ids:
            recent_note = f'避开了近 {RECENT_DAYS} 天穿过的单品'
        else:
            recent_note = '优先选了穿得比较少的单品'

        return f'当前 {temp:g}℃，{season_label}，推荐这套{occasion_note}{band_word}搭配{extra_note}。{recent_note}（含：{types}）'

    # ---------------- 温度 -> 季节 ----------------
    @staticmethod
    def _season_band(temp: float) -> tuple:
        """
        温度分段映射季节
        :return: (季节列表, 季节标签, 风格词)
        """
        if temp < 10:
            return ['冬'], '冬季', '保暖'
        if temp < 25:
            return ['春', '秋'], '春秋季', '轻薄'
        return ['夏'], '夏季', '清凉'

    # ---------------- 校验 ----------------
    @staticmethod
    def _parse_temperature(value: Any) -> float:
        """温度解析与范围校验"""
        if value is None or value == '':
            raise ApiError('temperature 不能为空', code=5002)
        try:
            temp = float(value)
        except (TypeError, ValueError):
            raise ApiError('temperature 必须为数字', code=5002)
        if temp < -50 or temp > 60:
            raise ApiError('temperature 超出合理范围（-50 ~ 60）', code=5002)
        return temp

    @staticmethod
    def _parse_occasion(value: Any) -> Optional[str]:
        """场合：空表示不限，否则须在枚举内"""
        occ = (value or '').strip() if isinstance(value, str) else ''
        if not occ:
            return None
        if occ not in ALLOWED_OCCASIONS:
            raise ApiError(f'场合不合法，可选：{"、".join(sorted(ALLOWED_OCCASIONS))}', code=5002)
        return occ
