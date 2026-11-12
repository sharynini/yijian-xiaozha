# -*- coding: utf-8 -*-
"""
图片指纹：用于「可能重复」检测（不依赖第三方库，只用 Pillow）

指纹由两部分组成，存成一个字符串 "<dhash 16 位十六进制>:<颜色签名 96 位十六进制>"：
1. dHash（差异哈希，64 位）：缩成 9×8 灰度图，比较每行相邻像素的明暗，得到衣物的「轮廓」。
   对缩放、压缩、轻微裁剪不敏感，比较时用汉明距离（不同的位数，0~64）。
2. 颜色签名：缩成 4×4 的平均颜色（48 个 0~255 的数），比较时用平均绝对差。
   只靠 dHash 时，轮廓相近的不同衣服（黑色阔腿裤和灰色百褶裙）会被误判，加上颜色可以排除。

两项都小于阈值才算「可能重复」。计算前先把透明背景（抠图结果）铺成白底，再裁到非白色区域，
保证只比较衣物本身，不受背景和留白影响。

在 281 张衣物照片上的实验（39340 对不同照片；同一照片缩小一半 + JPEG 质量 60 + 裁边 2% 模拟重复上传）：
dHash ≤ 10 且颜色 ≤ 16 时，重复上传识别率约 96%，不同照片被误判的只有 4 对（约 0.01%）。
"""
from typing import Optional, Tuple

from PIL import Image, ImageOps

DHASH_SIZE = 8
COLOR_GRID = 4
WHITE_CUTOFF = 240          # 灰度 ≥ 240 视为白底 / 留白


def _prepare(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    im = im.convert('RGB')
    mask = im.convert('L').point(lambda p: 255 if p < WHITE_CUTOFF else 0)
    box = mask.getbbox()
    return im.crop(box) if box else im


def _dhash(im: Image.Image) -> int:
    g = im.convert('L').resize((DHASH_SIZE + 1, DHASH_SIZE), Image.LANCZOS)
    px = g.tobytes()
    bits = 0
    for r in range(DHASH_SIZE):
        row = r * (DHASH_SIZE + 1)
        for c in range(DHASH_SIZE):
            bits = (bits << 1) | (px[row + c] > px[row + c + 1])
    return bits


def compute(path: str) -> Optional[str]:
    """计算图片指纹；文件打不开或不是图片时返回 None（不影响入库）"""
    try:
        with Image.open(path) as raw:
            im = _prepare(raw)
            dh = _dhash(im)
            color = im.resize((COLOR_GRID, COLOR_GRID), Image.BOX).tobytes()
    except Exception:  # noqa: BLE001  图片损坏等情况：没有指纹，只是不参与重复检测
        return None
    return f'{dh:016x}:{color.hex()}'


def distance(a: str, b: str) -> Optional[Tuple[int, float]]:
    """返回 (dHash 汉明距离, 平均颜色差)；格式不对时返回 None"""
    try:
        ha, ca = a.split(':')
        hb, cb = b.split(':')
        ham = bin(int(ha, 16) ^ int(hb, 16)).count('1')
        va, vb = bytes.fromhex(ca), bytes.fromhex(cb)
    except (AttributeError, ValueError):
        return None
    if len(va) != len(vb) or not va:
        return None
    return ham, sum(abs(x - y) for x, y in zip(va, vb)) / len(va)


def is_similar(a: Optional[str], b: Optional[str], max_hash: int, max_color: float) -> bool:
    if not a or not b:
        return False
    d = distance(a, b)
    return d is not None and d[0] <= max_hash and d[1] <= max_color
