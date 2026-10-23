# -*- coding: utf-8 -*-
"""
统一异常处理

- ApiError：业务代码中主动抛出的异常，自动转换为统一错误响应
- HTTPException：404/405 等框架级错误，保留 HTTP 状态码、统一响应体
- Exception：兜底捕获所有未处理异常，返回 500，避免堆栈泄露给前端
"""
from flask import Flask, jsonify, current_app, request
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """业务异常：在视图/服务层 raise ApiError('用户名已存在', code=1001) 即可"""

    def __init__(self, msg: str = '业务处理失败', code: int = 400, http_status: int = 200):
        super().__init__(msg)
        self.msg = msg
        self.code = code
        self.http_status = http_status


def _body(code: int, msg: str):
    return {'code': code, 'msg': msg, 'data': None}


def register_error_handlers(app: Flask) -> None:
    """注册全局异常处理器"""

    @app.errorhandler(ApiError)
    def handle_api_error(e: ApiError):
        # 业务错误也记日志，尤其是 4xx 参数错误 / 权限错误
        current_app.logger.warning(
            'ApiError code=%d http=%d msg=%s path=%s',
            e.code, e.http_status, e.msg, request.path,
        )
        resp = jsonify(_body(e.code, e.msg))
        resp.status_code = e.http_status
        return resp

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        # 框架级 HTTP 错误（404/405/413 等）：HTTP 状态码原样保留，响应体统一
        resp = jsonify(_body(e.code or 500, e.name))
        resp.status_code = e.code or 500
        return resp

    @app.errorhandler(Exception)
    def handle_unexpected_exception(e: Exception):
        # 兜底：记录完整堆栈日志，仅向前端返回通用提示
        current_app.logger.exception('Unhandled exception: %s', e)
        resp = jsonify(_body(500, '服务器内部错误'))
        resp.status_code = 500
        return resp


def register_jwt_handlers(jwt) -> None:
    """JWT 相关错误统一为一致的响应格式"""

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify(_body(401, f'缺少或非法的认证信息：{reason}')), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify(_body(401, f'Token 无效：{reason}')), 401

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return jsonify(_body(401, '登录已过期，请重新登录')), 401

    @jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return jsonify(_body(401, 'Token 已失效')), 401
