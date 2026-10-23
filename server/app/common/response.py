# -*- coding: utf-8 -*-
"""
统一响应格式工具

约定返回结构：
    成功: { "code": 0, "msg": "ok", "data": {...} }
    失败: { "code": <非0业务码>, "msg": "<错误描述>", "data": null }

业务失败默认 HTTP 状态码仍为 200，由前端按 code 判断；
框架级错误（404/500 等）在 errors.py 中处理，保留其 HTTP 状态码。
"""
from typing import Any, Optional

from flask import jsonify


def success(data: Any = None, msg: str = 'ok'):
    """成功响应"""
    return jsonify({'code': 0, 'msg': msg, 'data': data})


def error(msg: str = 'error', code: int = 400, http_status: int = 200, data: Optional[Any] = None):
    """
    业务失败响应
    :param msg: 错误描述（可直接展示给用户）
    :param code: 业务错误码，非 0
    :param http_status: HTTP 状态码，默认 200
    """
    resp = jsonify({'code': code, 'msg': msg, 'data': data})
    resp.status_code = http_status
    return resp
