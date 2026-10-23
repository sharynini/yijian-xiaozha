# -*- coding: utf-8 -*-
"""
开发环境启动入口
    python run.py
"""
import os

from dotenv import load_dotenv

from app import create_app

# 优先加载 .env 文件中的环境变量（override=True 会覆盖系统已有的同名环境变量）
load_dotenv(override=True)

app = create_app(os.getenv('FLASK_CONFIG', 'default'))

if __name__ == '__main__':
    # 注意：macOS 的 AirPlay 接收器默认占用 5000 端口，故开发端口使用 5001
    app.run(host='0.0.0.0', port=5001)
