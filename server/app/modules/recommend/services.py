# -*- coding: utf-8 -*-
"""
今日穿搭推荐业务逻辑层（基于规则，无 AI / 无外部依赖）

规则：
  1. 依据温度映射季节：<10℃ 冬；10~25℃ 春秋；>=25℃ 夏（"全季"衣物始终参与）
  2. 仅使用当前用户、未软删除、状态为"正常"的对应季节衣物
  3. 组合模板：上装 + 下装；若该季节有外套则附加一件外套
  4. 单品按 wear_count 升序优先（穿着次数越少越优先推荐）
  5. 最多生成 3 套互不重复的搭配，不足则返回实际套数
"""
from typing import Any, Dict, List

from app.common.errors import ApiError
from app.models.item import Item

MAX_OUTFITS = 3
ALL_SEASON = '全季'


class RecommendService:
    """基于规则的今日推荐"""

    # ---------------- 入口 ----------------
    @staticmethod
    def recommend(user_id: int, temperature: Any) -> Dict[str, Any]:
        """
        生成今日推荐
        :param temperature: 当前温度（数字）
        :return: { temperature, seasons, season_label, total_candidates, count, list }
        :raises ApiError: temperature 参数错误
        """
        temp = RecommendService._parse_temperature(temperature)
        seasons, season_label, band_word = RecommendService._season_band(temp)

        # 1. 拉取候选衣物（对应季节 + 全季）
        candidates = (
            Item.query
            .filter(
                Item.user_id == user_id,
                Item.deleted_at.is_(None),
                Item.status == '正常',
                Item.season.in_(seasons + [ALL_SEASON]),
            )
            .order_by(Item.wear_count.asc(), Item.id.asc())
            .all()
        )

        # 2. 按类型分组（均已按 wear_count 升序）
        tops = [it for it in candidates if it.type == '上装']
        bottoms = [it for it in candidates if it.type == '下装']
        outers = [it for it in candidates if it.type == '外套']

        # 3. 生成搭配
        combos = RecommendService._build_combos(tops, bottoms, outers)

        result = [
            {
                'items': [it.to_dict() for it in combo['items']],
                'reason': RecommendService._build_reason(temp, season_label, band_word, combo),
            }
            for combo in combos
        ]

        return {
            'temperature': temp,
            'seasons': seasons,
            'season_label': season_label,
            'total_candidates': len(candidates),
            'count': len(result),
            'list': result,
        }

    # ---------------- 组合生成 ----------------
    @staticmethod
    def _build_combos(tops: List[Item], bottoms: List[Item], outers: List[Item]) -> List[Dict[str, Any]]:
        """
        生成最多 MAX_OUTFITS 套互不重复的搭配
        规则：上装 + 下装（必需），有外套则附一件（可选）
        遍历"上装 × 下装"组合，取前 MAX_OUTFITS 套不重复结果
        """
        if not tops or not bottoms:
            # 缺少上装或下装，无法组成最基本搭配
            return []

        combos: List[Dict[str, Any]] = []
        seen = set()
        outer_idx = 0

        for top in tops:
            for bottom in bottoms:
                outer = outers[outer_idx % len(outers)] if outers else None
                outer_idx += 1

                items = [top, bottom] + ([outer] if outer else [])
                key = frozenset(it.id for it in items)
                if key in seen:
                    continue
                seen.add(key)
                combos.append({'items': items})

                if len(combos) >= MAX_OUTFITS:
                    return combos

        return combos

    # ---------------- 推荐理由 ----------------
    @staticmethod
    def _build_reason(temp: float, season_label: str, band_word: str, combo: Dict[str, Any]) -> str:
        """拼接简单可解释的推荐理由"""
        items = combo['items']
        types = '、'.join(it.type for it in items)
        has_outer = any(it.type == '外套' for it in items)
        outer_note = '，并配了外套' if has_outer else ''

        return (
            f"当前温度 {temp}℃，{season_label}，推荐这套{band_word}搭配{outer_note}。"
            f"（含：{types}；优先选择了穿着次数较少的单品）"
        )

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
