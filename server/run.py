# -*- coding: utf-8 -*-
"""
开发环境启动入口
    python run.py
"""
import os

from dotenv import load_dotenv

# 必须先加载 .env，再导入 app：config.py 在被导入时就会读取环境变量
# （override=True 会覆盖系统已有的同名环境变量）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

from app import create_app  # noqa: E402

app = create_app(os.getenv('FLASK_CONFIG', 'default'))

if __name__ == '__main__':
    # 注意：macOS 的 AirPlay 接收器默认占用 5000 端口，故开发端口使用 5001
    app.run(host='0.0.0.0', port=5001)
