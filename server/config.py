# -*- coding: utf-8 -*-
"""
全局配置文件
优先读取环境变量，缺省时使用开发环境默认值
"""
import os

from sqlalchemy.pool import StaticPool


def _build_mysql_uri() -> str:
    """拼接 MySQL 连接串。账号口令必须来自环境变量，禁止代码内弱默认。"""
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST', '127.0.0.1')
    port = os.getenv('DB_PORT', '3306')
    database = os.getenv('DB_NAME', 'smart_wardrobe')
    if not user or password is None:
        # 测试配置会覆盖 URI；非测试环境在 create_app 里还会再校验密钥
        user = user or ''
        password = password or ''
    return f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4'


def _upload_folder() -> str:
    server_dir = os.path.dirname(os.path.abspath(__file__))
    raw = (os.getenv('UPLOAD_FOLDER') or '').strip()
    if not raw:
        return os.path.join(server_dir, 'uploads')
    return raw if os.path.isabs(raw) else os.path.abspath(os.path.join(server_dir, raw))


class Config:
    """基础配置。SECRET_KEY / JWT_SECRET_KEY 必须从环境变量读取。"""
    SECRET_KEY = os.getenv('SECRET_KEY')
    JSON_AS_ASCII = False
    JSON_SORT_KEYS = False

    SQLALCHEMY_DATABASE_URI = _build_mysql_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    UPLOAD_FOLDER = _upload_folder()
    # 图片对外访问的域名前缀（如 https://api.example.com）；留空则用当前请求的域名
    PUBLIC_BASE_URL = (os.getenv('PUBLIC_BASE_URL') or '').strip().rstrip('/')

    # 和风天气（控制台 → 项目管理 获取）；未配置时首页退回手动调温度
    QWEATHER_API_KEY = os.getenv('QWEATHER_API_KEY', '')
    QWEATHER_API_HOST = os.getenv('QWEATHER_API_HOST', '')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 60 * 60 * 24 * 7))
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'


class DevelopmentConfig(Config):
    """开发环境"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境（预留）"""
    DEBUG = False


class TestingConfig(Config):
    """pytest 使用内存 SQLite，不连业务库"""
    TESTING = True
    DEBUG = True
    SECRET_KEY = 'pytest-only-secret'
    PUBLIC_BASE_URL = ''  # 测试固定用请求域名，不受本机环境变量影响
    JWT_SECRET_KEY = 'pytest-only-jwt-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }


# 环境名 -> 配置类 映射
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
