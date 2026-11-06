# -*- coding: utf-8 -*-
"""限流：登录 / 注册 / 微信登录按 IP，上传按用户；测试环境默认关闭，这里单独打开。"""
import io

import pytest
from PIL import Image

from app.common import ratelimit
from app.common.ratelimit import RateLimiter


@pytest.fixture
def limits_on(app):
    app.config['RATELIMIT_ENABLED'] = True
    ratelimit.reset_all()
    yield
    ratelimit.reset_all()


def _login(client, ip='10.0.0.1'):
    return client.post('/api/auth/login', json={'account': 'nobody', 'password': 'x'},
                       environ_base={'REMOTE_ADDR': ip})


def test_login_limited_per_ip(client, limits_on):
    for _ in range(10):
        assert _login(client).get_json()['code'] == 1003
    resp = _login(client)
    assert resp.status_code == 429
    assert resp.get_json()['code'] == 429
    # 其它 IP 不受影响
    assert _login(client, ip='10.0.0.2').get_json()['code'] == 1003


def test_register_limited(client, limits_on):
    for i in range(10):
        client.post('/api/auth/register', json={'username': f'u{i}x', 'email': f'u{i}@e.com', 'password': 'secret1'})
    resp = client.post('/api/auth/register', json={'username': 'last1', 'email': 'last@e.com', 'password': 'secret1'})
    assert resp.status_code == 429


def test_wx_login_limited(app, client, limits_on):
    app.config['WX_APPID'] = ''
    for _ in range(20):
        assert client.post('/api/auth/wx-login', json={'code': 'c'}).get_json()['code'] == 1006
    assert client.post('/api/auth/wx-login', json={'code': 'c'}).status_code == 429


def test_disabled_in_testing_by_default(client):
    for _ in range(15):
        assert _login(client).status_code == 200


def test_upload_limited_per_user(app, client, auth_header, tmp_path, limits_on):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    app.config['UPLOAD_RATE_LIMIT_PER_HOUR'] = 2

    def upload():
        buf = io.BytesIO()
        Image.new('RGB', (4, 4)).save(buf, 'PNG')
        buf.seek(0)
        return client.post('/api/upload', data={'file': (buf, 'a.png')}, headers=auth_header,
                           content_type='multipart/form-data')

    assert upload().get_json()['code'] == 0
    assert upload().get_json()['code'] == 0
    assert upload().status_code == 429


def test_window_expires(monkeypatch, app):
    limiter = RateLimiter('unit_test', limit=1, window_seconds=60)
    now = [1000.0]
    monkeypatch.setattr(ratelimit.time, 'time', lambda: now[0])
    with app.app_context():
        app.config['RATELIMIT_ENABLED'] = True
        limiter.check('k', 'too many')
        with pytest.raises(Exception):
            limiter.check('k', 'too many')
        now[0] += 61
        limiter.check('k', 'too many')   # 窗口过期后恢复
