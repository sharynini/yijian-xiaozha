# -*- coding: utf-8 -*-
"""
文件上传模块

- POST /api/upload              上传图片（需 JWT 鉴权），返回可直接访问的地址
- GET  /uploads/<filename>      读取已上传的图片（开发环境由 Flask 提供；生产环境由 nginx 直接提供）

上传处理：
  1. 每用户每小时最多 UPLOAD_RATE_LIMIT_PER_HOUR 张（app/common/ratelimit.py）
  2. 用 Pillow 打开校验，必须真的是 JPEG / PNG / WEBP / GIF 图片；文件扩展名按实际格式决定，
     不信任客户端给的文件名
  3. 去掉 EXIF 等元数据（手机照片里可能有拍摄地点 GPS），并按 EXIF 方向把图片转正
  4. 最长边超过 UPLOAD_MAX_SIDE 时等比缩小
  GIF 可能是动图，重新编码会丢帧，因此只校验不改写（GIF 一般不带 EXIF）

说明：该蓝图注册时不带 url_prefix，两条路由的完整路径在上面直接写死，
      因为「业务接口」与「静态资源」前缀不同（/api/... 与 /uploads/...）。
"""
import io
import os
import uuid

from flask import Blueprint, current_app, request, send_from_directory
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.common.errors import ApiError
from app.common.media import UPLOAD_PREFIX, to_public_url
from app.common.ratelimit import RateLimiter
from app.common.response import success

upload_bp = Blueprint('upload', __name__)

# 允许的扩展名（只做第一道粗筛，最终以图片实际格式为准）
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
# Pillow 识别出的格式 → 保存用的扩展名
EXT_BY_FORMAT = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}
# 防「解压炸弹」：像素数上限（约 8000×5000）
MAX_PIXELS = 40_000_000

# 每用户每小时上传张数，limit 在第一次使用时按配置设定
UPLOAD_LIMIT = RateLimiter('upload', limit=60, window_seconds=3600)


def _ext_of(filename: str) -> str:
    """取文件扩展名（小写，不含点）"""
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def _process_image(raw: bytes):
    """
    校验并清洗图片
    :return: (处理后的字节, 扩展名)
    :raises ApiError: 6001 不是有效图片 / 图片过大
    """
    from PIL import Image, ImageOps

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            width, height = probe.size
            probe.verify()          # 检查文件结构是否完整
    except Exception:
        raise ApiError('文件不是有效的图片，请换一张', code=6001)

    ext = EXT_BY_FORMAT.get(fmt or '')
    if not ext:
        raise ApiError('图片格式不支持，仅支持 jpg、png、webp、gif', code=6001)
    if width * height > MAX_PIXELS:
        raise ApiError('图片尺寸太大了，请换一张', code=6001)
    if fmt == 'GIF':
        return raw, ext

    max_side = int(current_app.config.get('UPLOAD_MAX_SIDE') or 2048)
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im = ImageOps.exif_transpose(im)        # 按拍摄方向转正，之后丢弃 EXIF
            if max(im.size) > max_side:
                im.thumbnail((max_side, max_side))
            if fmt == 'JPEG' and im.mode not in ('RGB', 'L'):
                im = im.convert('RGB')
            out = io.BytesIO()
            # 不传 exif / icc_profile 等参数，元数据就不会写入新文件
            if fmt == 'JPEG':
                im.save(out, 'JPEG', quality=88, optimize=True)
            elif fmt == 'PNG':
                im.save(out, 'PNG', optimize=True)
            else:
                im.save(out, 'WEBP', quality=88)
            return out.getvalue(), ext
    except ApiError:
        raise
    except Exception:
        current_app.logger.exception('处理上传图片失败')
        raise ApiError('图片处理失败，请换一张', code=6001)


@upload_bp.post('/api/upload')
@jwt_required()
def upload_image():
    """
    上传图片
    Header: Authorization: Bearer <token>
    Body: multipart/form-data，文件字段名固定为 file
    返回: { code: 0, data: {
              url:  'https://api.example.com/uploads/1_ab12....jpg',   # 完整地址，前端直接展示/提交
              path: '/uploads/1_ab12....jpg'                           # 库里实际保存的相对路径
          } }
    """
    user_id = int(get_jwt_identity())

    file = request.files.get('file')
    if file is None or not (file.filename or '').strip():
        raise ApiError('请选择要上传的图片', code=6001)

    if _ext_of(file.filename) not in ALLOWED_EXTENSIONS:
        raise ApiError('图片格式不支持，仅支持 jpg、jpeg、png、webp、gif', code=6001)

    UPLOAD_LIMIT.limit = int(current_app.config.get('UPLOAD_RATE_LIMIT_PER_HOUR') or 60)
    UPLOAD_LIMIT.check(str(user_id), '上传太频繁了，请稍后再试')

    data, ext = _process_image(file.read())

    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)

    # 文件名加 user_id 前缀（注销时按前缀删除），uuid 保证不重名、不可猜
    filename = f'{user_id}_{uuid.uuid4().hex}.{ext}'
    with open(os.path.join(upload_dir, filename), 'wb') as f:
        f.write(data)

    # 库里只存相对路径；返回完整地址给前端展示（前端提交回来时后端会再转回相对路径）
    path = f'{UPLOAD_PREFIX}{filename}'
    return success(data={'url': to_public_url(path), 'path': path}, msg='上传成功')


@upload_bp.get('/uploads/<path:filename>')
def serve_upload(filename: str):
    """读取已上传的图片（send_from_directory 自带路径穿越防护）"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
