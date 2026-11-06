# -*- coding: utf-8 -*-
"""GET /api/health、生产配置启动检查、反向代理真实 IP。"""
from unittest.mock import patch

from app import create_app


def test_health_ok(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    assert resp.get_json()['data'] == {'status': 'ok', 'database': 'ok'}


def test_health_db_down(client):
    with patch('app.db.session.execute', side_effect=Exception('down')):
        resp = client.get('/api/health')
    assert resp.status_code == 503
    assert resp.get_json()['data']['database'] == 'error'


def test_production_warns_missing_config(monkeypatch, capsys):
    """生产配置漏配时打警告（输出到标准输出），并且不注册调试台 / 测试接口"""
    import config
    monkeypatch.delenv('ALLOWED_ORIGINS', raising=False)
    monkeypatch.setattr(config.ProductionConfig, 'SECRET_KEY', 'x')
    monkeypatch.setattr(config.ProductionConfig, 'JWT_SECRET_KEY', 'y')
    monkeypatch.setattr(config.ProductionConfig, 'PUBLIC_BASE_URL', '')
    monkeypatch.setattr(config.ProductionConfig, 'TRUST_PROXY', False)
    monkeypatch.setattr(config.ProductionConfig, 'WX_APPID', '')

    app = create_app('production')
    out = capsys.readouterr().out

    assert app.debug is False
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert '/api/v1/test/ping' not in rules and '/' not in rules
    assert '/api/health' in rules
    for key in ('PUBLIC_BASE_URL', 'ALLOWED_ORIGINS', 'TRUST_PROXY', 'WX_APPID'):
        assert key in out


def test_proxy_fix_uses_forwarded_ip(monkeypatch):
    import config
    monkeypatch.setattr(config.TestingConfig, 'TRUST_PROXY', True)
    app = create_app('testing')
    seen = {}

    @app.get('/__ip')
    def _ip():
        from flask import request
        seen['ip'] = request.remote_addr
        return 'ok'

    app.test_client().get('/__ip', headers={'X-Forwarded-For': '203.0.113.9'}, environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert seen['ip'] == '203.0.113.9'
