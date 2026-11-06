# -*- coding: utf-8 -*-
"""
生产环境入口（给 gunicorn 用）
    venv/bin/gunicorn -c gunicorn.conf.py wsgi:app

与 run.py 的区别：
  - 默认以 production 配置启动（关闭调试、不注册调试台与测试接口、启动时检查关键配置）
  - .env 不覆盖服务器上已经存在的同名环境变量（systemd 里设置的优先）
本机开发仍然用 python run.py
"""
import os

from dotenv import load_dotenv

# 必须先加载 .env，再导入 app：config.py 在被导入时就会读取环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=False)

from app import create_app  # noqa: E402

app = create_app(os.getenv('FLASK_CONFIG') or 'production')
