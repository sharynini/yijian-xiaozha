# -*- coding: utf-8 -*-
"""
AI 能力：
  - AiService.recognize_item   识别衣物（阿里云百炼 · 通义千问视觉模型，OpenAI 兼容接口）
  - CutoutService.cutout        本地抠图（rembg），去掉背景后另存为透明 PNG

识别衣物：

流程：
  1. 只接受当前用户自己上传到本站的图片（/uploads/<user_id>_xxx.jpg），从磁盘读取后转 base64
  2. 让模型只在固定选项里选择类型 / 颜色 / 季节 / 场合，并只输出 JSON
  3. 后端再校验一遍：不在选项里的值一律丢弃（返回 null），前端只自动填合法值

说明：
  - API Key 只保存在后端环境变量，前端拿不到
  - 只用 Python 标准库发请求，不新增依赖
  - 同一用户每小时最多识别 RATE_LIMIT 次，防止额度被刷
"""
import base64
import json
import os
import re
import threading
import time
import uuid
import urllib.error
import urllib.request
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional

from flask import current_app

from app.common.errors import ApiError
from app.common.media import UPLOAD_PREFIX, to_public_url, to_storage_path
from app.modules.item.services import ALLOWED_OCCASIONS, ALLOWED_SEASONS, ALLOWED_TYPES

# 颜色选项与前端 utils/constants.js 的 COLORS 保持一致
ALLOWED_COLORS = (
    '黑色', '白色', '灰色', '米色', '卡其', '棕色', '蓝色', '牛仔蓝',
    '绿色', '红色', '粉色', '紫色', '黄色', '橙色', '花色',
)

# 让模型按固定顺序看选项（集合无序，这里写成元组）
TYPE_OPTIONS = ('上装', '下装', '连衣裙', '外套', '鞋子', '包包', '帽子', '配饰')
SEASON_OPTIONS = ('春', '夏', '秋', '冬', '全季')
OCCASION_OPTIONS = ('日常', '工作', '运动', '正式')

MIME_BY_EXT = {
    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
    'webp': 'image/webp', 'gif': 'image/gif',
}

# 频率限制默认值（可在 config / .env 中覆盖，见 AI_RECOGNIZE_LIMIT_PER_HOUR 等配置项）。
# 批量上传一次可能有二三十件，所以每小时额度放宽；再加一个 24 小时总上限，防止被刷导致 AI 费用失控
RATE_LIMIT = 100                # 每用户每小时最多识别次数
RATE_LIMIT_PER_DAY = 300        # 每用户 24 小时内最多识别次数
RATE_WINDOW_SECONDS = 3600
DAY_WINDOW_SECONDS = 24 * 3600
REQUEST_TIMEOUT_SECONDS = 30

# 进程内频率记录：{user_id: deque[时间戳]}（小时窗口、24 小时窗口各一份）
_calls: Dict[int, Deque[float]] = defaultdict(deque)
_daily_calls: Dict[int, Deque[float]] = defaultdict(deque)

PROMPT = (
    '你是衣物识别助手。请看图片中的这件衣物（如有多件，只看最主要的一件），'
    '从下面给定的选项中各选一个最合适的值，只输出一个 JSON 对象，不要输出任何其它文字。\n'
    f'type 只能是：{"、".join(TYPE_OPTIONS)}\n'
    f'color 只能是：{"、".join(ALLOWED_COLORS)}（多种颜色或有图案选「花色」）\n'
    f'season 只能是：{"、".join(SEASON_OPTIONS)}（四季都能穿选「全季」）\n'
    f'occasion 只能是：{"、".join(OCCASION_OPTIONS)}\n'
    '如果图片里不是衣物或完全无法判断某一项，该项填 null。\n'
    '输出格式示例：{"type":"上装","color":"白色","season":"夏","occasion":"日常"}'
)


class AiService:
    """AI 识别衣物"""

    @staticmethod
    def recognize_item(user_id: int, image_url: Any) -> Dict[str, Optional[str]]:
        """
        :return: { type, color, season, occasion }，识别不出或不合法的项为 None
        :raises ApiError: 8001 未配置 / 8002 图片无效 / 8003 识别失败 / 8004 太频繁
        """
        api_key = (current_app.config.get('DASHSCOPE_API_KEY') or '').strip()
        if not api_key:
            raise ApiError('AI 识别服务未配置', code=8001)

        path = AiService._resolve_own_upload(user_id, image_url)
        AiService._check_rate_limit(user_id, 'recognize')

        with open(path, 'rb') as f:
            raw = f.read()
        ext = path.rsplit('.', 1)[-1].lower()
        data_url = f'data:{MIME_BY_EXT.get(ext, "image/jpeg")};base64,{base64.b64encode(raw).decode()}'

        content = AiService._call_model(api_key, data_url)
        return AiService._parse_result(content)

    # ---------------- 图片校验 ----------------
    @staticmethod
    def _resolve_own_upload(user_id: int, image_url: Any) -> str:
        """只允许识别本人上传到本站的图片，返回磁盘绝对路径"""
        path = to_storage_path(image_url) if isinstance(image_url, str) else None
        if not path or not path.startswith(UPLOAD_PREFIX):
            raise ApiError('只能识别本站上传的图片', code=8002)

        filename = path[len(UPLOAD_PREFIX):]
        # 文件名形如 <user_id>_<uuid>.<ext>；禁止目录穿越
        if '/' in filename or '\\' in filename or not filename.startswith(f'{user_id}_'):
            raise ApiError('只能识别自己上传的图片', code=8002)
        if filename.rsplit('.', 1)[-1].lower() not in MIME_BY_EXT:
            raise ApiError('图片格式不支持', code=8002)

        full = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if not os.path.isfile(full):
            raise ApiError('图片不存在，请重新上传', code=8002)
        return full

    @staticmethod
    def _check_rate_limit(user_id: int, kind: str = 'recognize') -> None:
        """
        按用户做两级限流：每小时上限 + 24 小时总上限（滑动窗口，进程内计数）
        :param kind: recognize（AI 识别）或 cutout（本地抠图）
        :raises ApiError: 8004 超出额度
        """
        if kind == 'cutout':
            hour_store, day_store = _cutout_calls, _cutout_daily_calls
            hour_limit = int(current_app.config.get('AI_CUTOUT_LIMIT_PER_HOUR') or CUTOUT_RATE_LIMIT)
            day_limit = int(current_app.config.get('AI_CUTOUT_LIMIT_PER_DAY') or CUTOUT_RATE_LIMIT_PER_DAY)
            hour_msg = '抠图太频繁了，请稍后再试'
            day_msg = '今天的抠图次数已用完，明天再来吧（已保留原图）'
        else:
            hour_store, day_store = _calls, _daily_calls
            hour_limit = int(current_app.config.get('AI_RECOGNIZE_LIMIT_PER_HOUR') or RATE_LIMIT)
            day_limit = int(current_app.config.get('AI_RECOGNIZE_LIMIT_PER_DAY') or RATE_LIMIT_PER_DAY)
            hour_msg = '识别太频繁了，请稍后再试或手动选择'
            day_msg = '今天的 AI 识别次数已用完，明天再来或手动选择'

        now = time.time()
        hour = AiService._trim(hour_store[user_id], now - RATE_WINDOW_SECONDS)
        day = AiService._trim(day_store[user_id], now - DAY_WINDOW_SECONDS)
        if len(day) >= day_limit:
            raise ApiError(day_msg, code=8004)
        if len(hour) >= hour_limit:
            raise ApiError(hour_msg, code=8004)
        hour.append(now)
        day.append(now)

    @staticmethod
    def _trim(history: Deque[float], cutoff: float) -> Deque[float]:
        """丢掉窗口之外的旧记录"""
        while history and history[0] <= cutoff:
            history.popleft()
        return history

    # ---------------- 调用模型 ----------------
    @staticmethod
    def _call_model(api_key: str, data_url: str) -> str:
        base_url = (current_app.config.get('DASHSCOPE_BASE_URL') or '').rstrip('/')
        model = current_app.config.get('QWEN_VL_MODEL') or 'qwen3-vl-plus'
        body = {
            'model': model,
            'temperature': 0,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': data_url}},
                    {'type': 'text', 'text': PROMPT},
                ],
            }],
        }
        req = urllib.request.Request(
            f'{base_url}/chat/completions',
            data=json.dumps(body).encode('utf-8'),
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'ignore')[:300]
            current_app.logger.warning('Qwen-VL HTTP %s：%s', e.code, detail)
            raise ApiError('AI 识别暂时不可用，请手动选择', code=8003)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            current_app.logger.warning('Qwen-VL 请求失败：%s', e)
            raise ApiError('AI 识别暂时不可用，请手动选择', code=8003)

        try:
            return payload['choices'][0]['message']['content'] or ''
        except (KeyError, IndexError, TypeError):
            current_app.logger.warning('Qwen-VL 返回结构异常：%s', str(payload)[:300])
            raise ApiError('AI 识别结果异常，请手动选择', code=8003)

    # ---------------- 解析与校验 ----------------
    @staticmethod
    def _parse_result(content: Any) -> Dict[str, Optional[str]]:
        """从模型回复里抠出 JSON，并只保留合法选项"""
        if isinstance(content, list):          # 个别模型会返回分段内容
            content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
        match = re.search(r'\{.*\}', str(content), re.S)
        if not match:
            raise ApiError('AI 没认出来，请手动选择', code=8003)
        try:
            data = json.loads(match.group(0))
        except ValueError:
            raise ApiError('AI 没认出来，请手动选择', code=8003)
        if not isinstance(data, dict):
            raise ApiError('AI 没认出来，请手动选择', code=8003)

        def pick(key, allowed):
            value = data.get(key)
            value = value.strip() if isinstance(value, str) else None
            return value if value in allowed else None

        result = {
            'type': pick('type', ALLOWED_TYPES),
            'color': pick('color', ALLOWED_COLORS),
            'season': pick('season', ALLOWED_SEASONS),
            'occasion': pick('occasion', ALLOWED_OCCASIONS),
        }
        if not any(result.values()):
            raise ApiError('AI 没认出这是什么衣物，请手动选择', code=8003)
        return result


# =====================================================================
# 本地抠图（rembg）
# =====================================================================
CUTOUT_RATE_LIMIT = 120          # 每用户每小时最多抠图次数（本地计算，防止 CPU 被刷满；可用配置覆盖）
CUTOUT_RATE_LIMIT_PER_DAY = 400  # 每用户 24 小时内最多抠图次数
CUTOUT_ALPHA_THRESHOLD = 16      # 透明度低于它的像素视为背景（用于裁边）
CUTOUT_MIN_AREA_RATIO = 0.01     # 前景面积不到原图 1%，视为没抠出东西
CUTOUT_PADDING_RATIO = 0.04      # 裁边后四周留一点空白
CUTOUT_KEEP_RATIO = 0.3          # 只保留主体：面积不小于最大色块 30% 的色块才保留（一双鞋两只都留）
CUTOUT_LABEL_SIDE = 384          # 找连通块时把掩码缩到这个边长，兼顾速度与精度

_cutout_calls: Dict[int, Deque[float]] = defaultdict(deque)
_cutout_daily_calls: Dict[int, Deque[float]] = defaultdict(deque)
_session = None                  # rembg 模型会话：只加载一次，常驻内存
_session_lock = threading.Lock()


class CutoutService:
    """去掉衣物照片背景，生成透明背景 PNG"""

    @staticmethod
    def cutout(user_id: int, image_url: Any) -> Dict[str, str]:
        """
        :return: { url: 完整地址, path: /uploads/<user_id>_xxx.png }
        :raises ApiError: 8002 图片无效 / 8004 太频繁 / 8005 未安装 / 8006 没抠出衣物 / 8007 抠图失败
        """
        src = AiService._resolve_own_upload(user_id, image_url)
        AiService._check_rate_limit(user_id, 'cutout')

        try:
            from PIL import Image, ImageOps
        except ImportError:
            raise ApiError('抠图组件未安装，已保留原图', code=8005)

        max_side = int(current_app.config.get('CUTOUT_MAX_SIDE') or 1024)
        try:
            with Image.open(src) as im:
                image = ImageOps.exif_transpose(im).convert('RGB')
        except Exception:
            raise ApiError('图片无法读取，请换一张', code=8002)
        image.thumbnail((max_side, max_side))

        result = CutoutService._remove_background(image).convert('RGBA')
        result = CutoutService._keep_main_subject(result)
        cropped = CutoutService._crop_to_content(result)

        filename = f'{user_id}_{uuid.uuid4().hex}.png'
        cropped.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename), 'PNG', optimize=True)
        path = f'{UPLOAD_PREFIX}{filename}'
        return {'url': to_public_url(path), 'path': path}

    # ---------------- 内部 ----------------
    @staticmethod
    def _remove_background(image):
        """调用 rembg 去背景；rembg 用到时才导入，没装也不影响后端启动"""
        try:
            from rembg import new_session, remove
        except ImportError:
            raise ApiError('抠图组件未安装，已保留原图', code=8005)

        global _session
        try:
            with _session_lock:
                if _session is None:
                    model = current_app.config.get('REMBG_MODEL') or 'isnet-general-use'
                    current_app.logger.info('加载抠图模型 %s（首次会下载模型文件，可能较慢）', model)
                    _session = new_session(model)
            # 掩码后处理会把腋下、裤裆这类窄凹口当成小洞填上，默认关闭；需要时用 CUTOUT_POST_PROCESS 打开
            if current_app.config.get('CUTOUT_POST_PROCESS'):
                try:
                    return remove(image, session=_session, post_process_mask=True)
                except TypeError:
                    pass                 # 个别 rembg 版本不支持该参数，退回默认处理
            return remove(image, session=_session)
        except ApiError:
            raise
        except Exception as e:
            current_app.logger.exception('抠图失败：%s', e)
            raise ApiError('抠图失败（模型可能还没下载好），已保留原图', code=8007)

    @staticmethod
    def _keep_main_subject(image):
        """
        只保留主体：找出所有互不相连的前景色块，只留最大的那块，
        以及面积和它差不多的（≥ CUTOUT_KEEP_RATIO，比如一双鞋的另一只）；
        和衣服不相连的杯子、书、手机等杂物会被去掉。
        只用 Pillow + numpy（rembg 已自带），不额外引入 OpenCV；不可用时原样返回。
        """
        try:
            import numpy as np
            from PIL import Image, ImageDraw, ImageFilter
        except ImportError:
            return image

        rgba = np.array(image)
        h, w = rgba.shape[:2]
        fg = rgba[:, :, 3] >= CUTOUT_ALPHA_THRESHOLD

        # 在缩小的掩码上找连通块，速度快；结果再放大回原尺寸
        scale = min(1.0, CUTOUT_LABEL_SIDE / max(h, w))
        sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
        labels = Image.fromarray(fg.astype(np.uint8) * 255).resize((sw, sh), Image.NEAREST)

        areas = {}
        arr = np.array(labels)
        for label in range(1, 255):                    # 255 = 还没编号的前景，0 = 背景
            ys, xs = np.nonzero(arr == 255)
            if not len(ys):
                break
            ImageDraw.floodfill(labels, (int(xs[0]), int(ys[0])), label, thresh=0)
            arr = np.array(labels)
            areas[label] = int((arr == label).sum())

        if len(areas) <= 1:                            # 只有一个色块，无需处理
            return image

        biggest = max(areas.values())
        keep = [k for k, a in areas.items() if a >= biggest * CUTOUT_KEEP_RATIO]
        keep_small = Image.fromarray(np.isin(arr, keep).astype(np.uint8) * 255)
        # 稍微外扩一圈再放大，避免缩放时把衣服边缘误删
        keep_full = np.array(keep_small.filter(ImageFilter.MaxFilter(3)).resize((w, h), Image.NEAREST)) > 0

        rgba[:, :, 3] = np.where(keep_full, rgba[:, :, 3], 0)
        return Image.fromarray(rgba, 'RGBA')

    @staticmethod
    def _crop_to_content(image):
        """裁掉四周的透明区域，只留衣物本身（四周留少量空白）"""
        alpha = image.getchannel('A').point(lambda a: 255 if a >= CUTOUT_ALPHA_THRESHOLD else 0)
        bbox = alpha.getbbox()
        if not bbox:
            raise ApiError('没有识别到衣物，已保留原图', code=8006)

        left, top, right, bottom = bbox
        if (right - left) * (bottom - top) < image.width * image.height * CUTOUT_MIN_AREA_RATIO:
            raise ApiError('没有识别到衣物，已保留原图', code=8006)

        pad = int(max(right - left, bottom - top) * CUTOUT_PADDING_RATIO)
        return image.crop((
            max(0, left - pad), max(0, top - pad),
            min(image.width, right + pad), min(image.height, bottom + pad),
        ))
