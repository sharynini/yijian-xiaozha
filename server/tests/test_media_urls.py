# -*- coding: utf-8 -*-
"""图片地址：库里存相对路径，接口返回完整地址；生产环境不开放调试接口。"""
import io

import pytest

from app import create_app
from app.common.media import to_public_url, to_storage_path
from app.extensions import db
from app.models.item import Item
from app.models.wear_log import WearLog
from config import TestingConfig, config_map
from tests.conftest import make_item

LEGACY_URL = 'http://127.0.0.1:5001/uploads/1_legacy.jpg'
EXTERNAL_URL = 'https://cdn.example.com/uploads/x.jpg'


# ---------------- 工具函数 ----------------
def test_to_storage_path_rules(app):
    assert to_storage_path(LEGACY_URL) == '/uploads/1_legacy.jpg'
    assert to_storage_path('http://192.168.1.8:5001/uploads/a.png') == '/uploads/a.png'
    assert to_storage_path('/uploads/a.png') == '/uploads/a.png'
    assert to_storage_path(EXTERNAL_URL) == EXTERNAL_URL           # 外部链接不动
    assert to_storage_path('https://old.com/uploads/a.png', extra_hosts=['old.com']) == '/uploads/a.png'
    assert to_storage_path(None) is None


def test_to_public_url_uses_public_base(app):
    app.config['PUBLIC_BASE_URL'] = 'https://api.example.com'
    assert to_public_url('/uploads/a.png') == 'https://api.example.com/uploads/a.png'
    assert to_public_url(LEGACY_URL) == 'https://api.example.com/uploads/1_legacy.jpg'
    assert to_public_url(EXTERNAL_URL) == EXTERNAL_URL
    assert to_public_url(None) is None


# ---------------- 衣物 ----------------
def test_item_stores_relative_and_returns_absolute(client, auth_header, user):
    resp = client.post('/api/items', json={'image_url': LEGACY_URL, 'type': '上装'}, headers=auth_header)
    body = resp.get_json()

    assert body['code'] == 0
    assert body['data']['image_url'] == 'http://localhost/uploads/1_legacy.jpg'
    assert db.session.get(Item, body['data']['item_id']).image_url == '/uploads/1_legacy.jpg'


def test_item_update_normalizes_url(client, auth_header, user):
    item = make_item(user.id)
    resp = client.put(f'/api/items/{item.id}', json={'image_url': LEGACY_URL}, headers=auth_header)

    assert resp.get_json()['code'] == 0
    assert db.session.get(Item, item.id).image_url == '/uploads/1_legacy.jpg'


def test_item_external_url_kept(client, auth_header, user):
    resp = client.post('/api/items', json={'image_url': EXTERNAL_URL, 'type': '上装'}, headers=auth_header)
    body = resp.get_json()

    assert body['data']['image_url'] == EXTERNAL_URL
    assert db.session.get(Item, body['data']['item_id']).image_url == EXTERNAL_URL


def test_public_base_url_config(app, client, auth_header, user):
    app.config['PUBLIC_BASE_URL'] = 'https://api.example.com'
    make_item(user.id, image_url='/uploads/a.jpg')

    data = client.get('/api/items', headers=auth_header).get_json()['data']
    assert data['list'][0]['image_url'] == 'https://api.example.com/uploads/a.jpg'


# ---------------- 穿搭日记 ----------------
def test_wear_log_snapshot_and_photo_relative(client, auth_header, user):
    top = make_item(user.id, image_url=LEGACY_URL)      # 模拟迁移前的老数据
    bottom = make_item(user.id, type='下装', image_url='/uploads/b.jpg')

    resp = client.post('/api/wear-logs', json={
        'item_ids': [top.id, bottom.id],
        'photo_url': 'http://127.0.0.1:5001/uploads/photo.jpg',
    }, headers=auth_header)
    data = resp.get_json()['data']

    log = db.session.get(WearLog, data['log_id'])
    assert log.photo_url == '/uploads/photo.jpg'
    assert [it['image_url'] for it in log.items_snapshot] == ['/uploads/1_legacy.jpg', '/uploads/b.jpg']

    assert data['photo_url'] == 'http://localhost/uploads/photo.jpg'
    assert [it['image_url'] for it in data['items']] == [
        'http://localhost/uploads/1_legacy.jpg',
        'http://localhost/uploads/b.jpg',
    ]


# ---------------- 上传 ----------------
def test_upload_returns_url_and_path(app, client, auth_header, tmp_path):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    resp = client.post(
        '/api/upload',
        data={'file': (io.BytesIO(b'fake-image'), 'a.jpg')},
        headers=auth_header,
        content_type='multipart/form-data',
    )
    data = resp.get_json()['data']

    assert data['path'].startswith('/uploads/') and data['path'].endswith('.jpg')
    assert data['url'] == 'http://localhost' + data['path']
    assert (tmp_path / data['path'].rsplit('/', 1)[-1]).exists()


# ---------------- 调试接口开关 ----------------
def test_debug_routes_available_in_debug(client):
    assert client.get('/api/v1/test/ping').status_code == 200


@pytest.fixture
def prod_like_client(monkeypatch):
    class NoDebugConfig(TestingConfig):
        DEBUG = False

    monkeypatch.setitem(config_map, 'nodebug', NoDebugConfig)
    return create_app('nodebug').test_client()


def test_debug_routes_hidden_without_debug(prod_like_client):
    assert prod_like_client.get('/api/v1/test/ping').status_code == 404
    assert prod_like_client.get('/api/v1/test/db').status_code == 404
    assert prod_like_client.get('/').status_code == 404
