# -*- coding: utf-8 -*-
"""POST /api/auth/wx-login：未配置、参数、code 无效、新老用户、软删除后重新登录。微信接口全部 mock。"""
from datetime import datetime
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.user import User
from app.modules.auth.services import AuthService

FETCH = 'app.modules.auth.services.AuthService._fetch_wx_json'


@pytest.fixture
def configured(app):
    app.config['WX_APPID'] = 'wx-test-appid'
    app.config['WX_APPSECRET'] = 'wx-test-secret'


def _login(client, code='code-1'):
    return client.post('/api/auth/wx-login', json={'code': code}).get_json()


def test_not_configured(app, client):
    app.config['WX_APPID'] = ''
    app.config['WX_APPSECRET'] = ''
    assert _login(client)['code'] == 1006


def test_missing_code(client, configured):
    assert client.post('/api/auth/wx-login', json={}).get_json()['code'] == 1004
    assert _login(client, code='   ')['code'] == 1004


def test_invalid_code(client, configured):
    with patch(FETCH, return_value={'errcode': 40029, 'errmsg': 'invalid code'}):
        assert _login(client)['code'] == 1007


def test_wx_other_error(client, configured):
    with patch(FETCH, return_value={'errcode': 45011, 'errmsg': 'rate limit'}):
        assert _login(client)['code'] == 1008
    with patch(FETCH, return_value={}):
        assert _login(client)['code'] == 1008


def test_new_user_created(app, client, configured):
    with patch(FETCH, return_value={'openid': 'o-123', 'session_key': 'sk'}):
        body = _login(client)
    assert body['code'] == 0
    data = body['data']
    assert data['is_new'] is True
    assert data['access_token']
    assert data['user']['nickname'] == '衣橱主人'
    assert data['user']['username'].startswith('wx_')
    assert 'openid' not in data['user']          # openid 不对外暴露

    user = User.query.filter_by(openid='o-123').one()
    assert user.password_hash is None
    assert user.check_password('anything') is False


def test_existing_user_reused(app, client, configured):
    with patch(FETCH, return_value={'openid': 'o-123'}):
        first = _login(client)['data']
        second = _login(client, code='code-2')['data']
    assert second['is_new'] is False
    assert second['user']['user_id'] == first['user']['user_id']
    assert User.query.filter_by(openid='o-123').count() == 1


def test_token_works_for_profile(client, configured):
    with patch(FETCH, return_value={'openid': 'o-123'}):
        token = _login(client)['data']['access_token']
    body = client.get('/api/auth/profile', headers={'Authorization': f'Bearer {token}'}).get_json()
    assert body['code'] == 0
    assert body['data']['nickname'] == '衣橱主人'


def test_soft_deleted_user_gets_new_account(app, client, configured):
    with patch(FETCH, return_value={'openid': 'o-123'}):
        old_id = _login(client)['data']['user']['user_id']
        old = db.session.get(User, old_id)
        old.deleted_at = datetime.utcnow()
        db.session.commit()

        data = _login(client, code='code-2')['data']

    assert data['is_new'] is True
    assert data['user']['user_id'] != old_id
    assert db.session.get(User, old_id).openid is None


def test_password_login_unaffected_for_wx_user(client, configured):
    """微信账号没有密码，用它的内部用户名走账号密码登录必须失败"""
    with patch(FETCH, return_value={'openid': 'o-123'}):
        username = _login(client)['data']['user']['username']
    body = client.post('/api/auth/login', json={'account': username, 'password': ''}).get_json()
    assert body['code'] == 1004
    body = client.post('/api/auth/login', json={'account': username, 'password': 'whatever'}).get_json()
    assert body['code'] == 1003


def test_secret_not_logged_on_network_error(app, configured, caplog):
    """网络异常时日志里不能出现 AppSecret"""
    import urllib.error
    with app.test_request_context():
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('boom')):
            with pytest.raises(Exception):
                AuthService._code_to_openid('code-1')
    assert 'wx-test-secret' not in caplog.text
