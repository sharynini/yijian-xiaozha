# -*- coding: utf-8 -*-
"""
应用工厂：创建并装配 Flask 应用实例
"""
import logging
import os
import sys
import time

from flask import Flask, g, request
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config_map
from app.extensions import db, jwt, cors, migrate
from app.common.errors import register_error_handlers, register_jwt_handlers
from app.common.response import success
from app.modules.test.routes import test_bp
from app.modules.auth.routes import auth_bp
from app.modules.item.routes import item_bp
from app.modules.home.routes import home_bp
from app.modules.outfit.routes import outfit_bp
from app.modules.wear_log.routes import wear_log_bp
from app.modules.recommend.routes import recommend_bp
from app.modules.upload.routes import upload_bp
from app.modules.weather.routes import weather_bp
from app.modules.ai.routes import ai_bp


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


def _setup_logging(app: Flask) -> None:
    """日志统一输出到标准输出（gunicorn / systemd 会收集），级别来自 LOG_LEVEL"""
    level = getattr(logging, app.config.get('LOG_LEVEL') or 'INFO', logging.INFO)
    app.logger.setLevel(level)
    if not app.debug and not app.testing:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))
        app.logger.handlers = [handler]
        app.logger.propagate = False


def _check_production_config(app: Flask) -> None:
    """生产环境启动时检查容易漏配的项；只打警告，不阻止启动"""
    if not app.config.get('PUBLIC_BASE_URL'):
        app.logger.warning('生产环境未配置 PUBLIC_BASE_URL，图片地址会使用请求域名，HTTPS 反向代理下可能拼成 http://')
    if (os.getenv('ALLOWED_ORIGINS') or '*').strip() == '*':
        app.logger.warning('生产环境 ALLOWED_ORIGINS 仍为 *，建议改为实际前端域名（小程序请求不受影响，H5 受影响）')
    if not app.config.get('TRUST_PROXY'):
        app.logger.warning('生产环境未开启 TRUST_PROXY：部署在 nginx 后面时限流会把所有用户当成同一个 IP')
    if not app.config.get('WX_APPID') or not app.config.get('WX_APPSECRET'):
        app.logger.warning('未配置 WX_APPID / WX_APPSECRET，小程序微信登录不可用')


def _register_health(app: Flask) -> None:
    """GET /api/health：服务与数据库存活检查，给部署脚本 / 监控用（无需登录，不返回任何配置信息）"""

    @app.get('/api/health')
    def health():
        try:
            db.session.execute(text('SELECT 1'))
            database = 'ok'
        except Exception:
            app.logger.exception('健康检查：数据库不可用')
            database = 'error'
        body = success(data={'status': 'ok' if database == 'ok' else 'degraded', 'database': database})
        if database != 'ok':
            body.status_code = 503
        return body


def create_app(config_name: str = 'default') -> Flask:
    app = Flask(__name__)

    # 1. 加载配置
    resolved = config_map.get(config_name, config_map['default'])
    app.config.from_object(resolved)
    if config_name != 'testing':
        if not app.config.get('SECRET_KEY') or not app.config.get('JWT_SECRET_KEY'):
            raise RuntimeError('SECRET_KEY 与 JWT_SECRET_KEY 必须通过环境变量（server/.env）提供，禁止使用代码内弱默认值')

    _setup_logging(app)

    # 在 nginx 后面时信任一层代理，request.remote_addr / scheme 才是真实值
    if app.config.get('TRUST_PROXY'):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # 2. 初始化扩展
    db.init_app(app)
    jwt.init_app(app)
    # 迁移工具需要拿到全部模型的元数据，这里显式导入一次
    from app import models  # noqa: F401
    migrate.init_app(app, db)

    # CORS 来源来自环境变量 ALLOWED_ORIGINS（逗号分隔；* 表示全部）
    raw_origins = (os.getenv('ALLOWED_ORIGINS') or '*').strip()
    ALLOWED_ORIGINS = '*' if raw_origins == '*' else [x.strip() for x in raw_origins.split(',') if x.strip()]
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
    # 调试台（/）与测试接口（/api/v1/test/*）只在 DEBUG 模式下开放，生产环境不注册
    if app.config.get('DEBUG'):
        app.register_blueprint(test_bp, url_prefix='/api/v1/test')
        app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(item_bp, url_prefix='/api/items')
    app.register_blueprint(outfit_bp, url_prefix='/api/outfits')
    app.register_blueprint(wear_log_bp, url_prefix='/api/wear-logs')
    app.register_blueprint(recommend_bp, url_prefix='/api/recommend')
    app.register_blueprint(weather_bp, url_prefix='/api/weather')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    # upload 蓝图内部已写死完整路径（/api/upload、/uploads/<filename>），故不带 url_prefix
    app.register_blueprint(upload_bp)

    _register_health(app)

    # 4. 注册统一异常处理 & JWT 错误回调
    register_error_handlers(app)
    register_jwt_handlers(jwt)

    _register_cli(app)

    if config_name == 'production':
        _check_production_config(app)

    return app


def _register_cli(app: Flask) -> None:
    """命令行工具：flask <命令>"""

    @app.cli.command('backfill-image-fp')
    def backfill_image_fp():
        """给还没有图片指纹的衣物补算指纹（重复照片检测上线后执行一次）"""
        from app.modules.item.services import ItemService
        total, done = ItemService.backfill_fingerprints()
        print(f'处理 {total} 件衣物，成功计算 {done} 件指纹（其余为外部图片或文件缺失）')
