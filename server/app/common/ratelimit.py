# -*- coding: utf-8 -*-
"""
简单的滑动窗口限流（只用标准库，计数存在进程内存里）

用法：
    LOGIN_LIMIT = RateLimiter('login', limit=10, window_seconds=60)
    LOGIN_LIMIT.check(client_ip(), '登录太频繁了，请 1 分钟后再试')   # 超出时抛 ApiError（HTTP 429）

说明：
  - 部署为 gunicorn 单进程多线程（见 gunicorn.conf.py），计数在进程内共享；多进程时每个进程各自计数
  - 进程重启后计数清零
  - app.config['RATELIMIT_ENABLED'] 为 False 时不限流（测试环境默认关闭，限流测试里单独打开）
  - client_ip() 依赖 request.remote_addr；生产环境在 nginx 后面时需开启 TRUST_PROXY，
    由 ProxyFix 把 X-Forwarded-For 还原成真实客户端 IP（见 app/__init__.py）
"""
import threading
import time
from collections import deque
from typing import Deque, Dict

from flask import current_app, has_app_context, request

from app.common.errors import ApiError

RATE_LIMITED_CODE = 429

_registry: Dict[str, 'RateLimiter'] = {}


class RateLimiter:
    def __init__(self, name: str, limit: int, window_seconds: int):
        self.name = name
        self.limit = limit
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.time()
        _registry[name] = self

    def check(self, key: str, msg: str) -> None:
        """记一次访问；超出限制抛 ApiError(code=429, http 429)，这次不计数"""
        if has_app_context() and not current_app.config.get('RATELIMIT_ENABLED', True):
            return
        now = time.time()
        with self._lock:
            self._sweep(now)
            hits = self._hits.setdefault(key or 'unknown', deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                raise ApiError(msg, code=RATE_LIMITED_CODE, http_status=429)
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _sweep(self, now: float) -> None:
        """每个窗口清理一次过期的 key，避免长时间运行后内存一直增长"""
        if now - self._last_sweep < self.window:
            return
        self._last_sweep = now
        for key in [k for k, q in self._hits.items() if not q or now - q[-1] >= self.window]:
            del self._hits[key]


def reset_all() -> None:
    """测试用：清空所有限流计数"""
    for limiter in _registry.values():
        limiter.reset()


def client_ip() -> str:
    return request.remote_addr or 'unknown'
