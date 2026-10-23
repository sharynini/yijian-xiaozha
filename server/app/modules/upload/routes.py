# -*- coding: utf-8 -*-
"""
文件上传模块

- POST /api/upload              上传衣物图片（需 JWT 鉴权），返回可直接访问的绝对 URL
- GET  /uploads/<filename>      读取已上传的图片（静态托管）

说明：该蓝图注册时不带 url_prefix，两条路由的完整路径在上面直接写死，
      因为「业务接口」与「静态资源」前缀不同（/api/... 与 /uploads/...）。
"""
import os
import uuid

from flask import Blueprint, current_app, request, send_from_directory
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.common.errors import ApiError
from app.common.response import success

upload_bp = Blueprint('upload', __name__)

# 允许的图片扩展名
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}


def _ext_of(filename: str) -> str:
    """取文件扩展名（小写，不含点）"""
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


@upload_bp.post('/api/upload')
@jwt_required()
def upload_image():
    """
    上传图片
    Header: Authorization: Bearer <token>
    Body: multipart/form-data，文件字段名固定为 file
    返回: { code: 0, data: { url: 'http://127.0.0.1:5001/uploads/1_ab12....jpg' } }
    """
    user_id = int(get_jwt_identity())

    file = request.files.get('file')
    if file is None or not (file.filename or '').strip():
        raise ApiError('请选择要上传的图片', code=6001)

    ext = _ext_of(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ApiError('图片格式不支持，仅支持 jpg、jpeg、png、webp、gif', code=6001)

    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)

    # 文件名加 user_id 前缀便于排查，uuid 保证不重名
    filename = f'{user_id}_{uuid.uuid4().hex}.{ext}'
    file.save(os.path.join(upload_dir, filename))

    # host_url 形如 http://127.0.0.1:5001/，拼接后即为可直接访问的绝对地址
    url = f"{request.host_url.rstrip('/')}/uploads/{filename}"
    return success(data={'url': url}, msg='上传成功')


@upload_bp.get('/uploads/<path:filename>')
def serve_upload(filename: str):
    """读取已上传的图片（send_from_directory 自带路径穿越防护）"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
