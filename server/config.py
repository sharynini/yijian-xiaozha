# -*- coding: utf-8 -*-
"""
全局配置文件
优先读取环境变量，缺省时使用开发环境默认值
"""
import os


def _build_mysql_uri() -> str:
    """拼接 MySQL 连接串（PyMySQL 驱动，utf8mb4 编码）"""
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', 'root')
    host = os.getenv('DB_HOST', '127.0.0.1')
    port = os.getenv('DB_PORT', '3306')
    database = os.getenv('DB_NAME', 'smart_wardrobe')
    return f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4'


class Config:
    """基础配置（各环境通用）"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
    JSON_AS_ASCII = False          # JSON 响应支持中文
    JSON_SORT_KEYS = False

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = _build_mysql_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,      # 防止 MySQL 8 小时断连
        'pool_pre_ping': True,     # 取连接前先探活
    }

    # 文件上传（衣物图片）
    # 落盘目录：server/uploads/；对外访问前缀：/uploads/
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024   # 单个请求体最大 5MB

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-dev-secret-change-me')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 60 * 60 * 24 * 7))  # 默认 7 天（秒）
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'


class DevelopmentConfig(Config):
    """开发环境"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境（预留）"""
    DEBUG = False


# 环境名 -> 配置类 映射
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
