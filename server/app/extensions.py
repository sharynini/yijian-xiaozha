# -*- coding: utf-8 -*-
"""
扩展实例集中声明
在此处创建"未绑定 app"的扩展对象，避免循环导入；
真正绑定在应用工厂 create_app 中通过 init_app 完成。
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate

db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()
# 数据库迁移（Alembic）：flask --app run.py db migrate / upgrade
migrate = Migrate()
