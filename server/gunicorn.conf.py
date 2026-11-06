# -*- coding: utf-8 -*-
"""
gunicorn 配置（生产环境）
    cd server && venv/bin/gunicorn -c gunicorn.conf.py wsgi:app

为什么是 1 个进程 × 多线程：
  - 抠图模型（rembg）每个进程都要单独加载一份，常驻内存几百 MB
  - AI / 上传 / 登录限流和天气缓存都存在进程内存里，单进程时计数才准确
  - 接口多为数据库读写和等待外部接口（I/O 为主），线程足够；抠图计算在 onnxruntime 里会释放 GIL
访问量明显变大后，再把限流和缓存换成 Redis 并增加进程数。
"""
import os

# 只监听本机，由 nginx 对外提供 HTTPS 并转发进来
bind = os.getenv('GUNICORN_BIND', '127.0.0.1:5001')

workers = int(os.getenv('GUNICORN_WORKERS', '1'))
worker_class = 'gthread'
threads = int(os.getenv('GUNICORN_THREADS', '8'))

# 抠图首次加载模型 + 处理大图可能比较慢
timeout = 120
graceful_timeout = 30
keepalive = 5

# 进程处理一定数量请求后自动重启，防止内存缓慢增长（加随机抖动避免同时重启）
max_requests = 2000
max_requests_jitter = 200

# 日志输出到标准输出 / 标准错误，由 systemd（journalctl）收集
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms'

# 信任本机 nginx 传来的 X-Forwarded-* 头（应用内的 ProxyFix 由 TRUST_PROXY 控制）
forwarded_allow_ips = '127.0.0.1'
