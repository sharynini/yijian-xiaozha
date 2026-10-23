# -*- coding: utf-8 -*-
"""
应用工厂：创建并装配 Flask 应用实例
"""
import time

from flask import Flask, g, request

from config import config_map
from app.extensions import db, jwt, cors
from app.common.errors import register_error_handlers, register_jwt_handlers
from app.modules.test.routes import test_bp
from app.modules.auth.routes import auth_bp
from app.modules.item.routes import item_bp
from app.modules.home.routes import home_bp
from app.modules.outfit.routes import outfit_bp
from app.modules.wear_log.routes import wear_log_bp
from app.modules.recommend.routes import recommend_bp
from app.modules.upload.routes import upload_bp


def _register_request_logging(app: Flask) -> None:
    """轻量请求日志：method + path + status + latency；生产环境可降级为 DEBUG"""

    @app.before_request
    def _start_timer():
        g._start_at = time.time()

    @app.after_request
    def _log(response):
        latency_ms = (time.time() - g.get('_start_at', time.time())) * 1000
        level = 'warning' if response.status_code >= 400 else 'info'
        getattr(app.logger, level)(
            '%-4s %-40s → %d  %.1fms',
            request.method, request.path,
            response.status_code, latency_ms,
        )
        return response


def create_app(config_name: str = 'default') -> Flask:
    app = Flask(__name__)

    # 1. 加载配置
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # 2. 初始化扩展
    db.init_app(app)
    jwt.init_app(app)

    # CORS：开发期放开所有源；上线前把 ALLOWED_ORIGINS 换成具体域名白名单
    # ⚠️ 不要加 supports_credentials=True —— 我们用 Bearer token，不是 cookie
    ALLOWED_ORIGINS = '*'
    cors.init_app(app, resources={
        r'/api/*': {
            'origins': ALLOWED_ORIGINS,
            'methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            'allow_headers': ['Content-Type', 'Authorization'],
        },
        r'/uploads/*': {
            'origins': ALLOWED_ORIGINS,
            'methods': ['GET'],
        },
    })

    # 请求日志（method + path + status + latency）
    _register_request_logging(app)

    # 3. 注册蓝图
    app.register_blueprint(test_bp, url_prefix='/api/v1/test')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(item_bp, url_prefix='/api/items')
    app.register_blueprint(outfit_bp, url_prefix='/api/outfits')
    app.register_blueprint(wear_log_bp, url_prefix='/api/wear-logs')
    app.register_blueprint(recommend_bp, url_prefix='/api/recommend')
    # upload 蓝图内部已写死完整路径（/api/upload、/uploads/<filename>），故不带 url_prefix
    app.register_blueprint(upload_bp)
    app.register_blueprint(home_bp)

    # 4. 注册统一异常处理 & JWT 错误回调
    register_error_handlers(app)
    register_jwt_handlers(jwt)

    return app
