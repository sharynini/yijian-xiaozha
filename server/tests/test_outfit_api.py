# -*- coding: utf-8 -*-
"""搭配方案：创建（含自动命名、布局）、列表、详情、更新、删除、用户隔离、衣物被删后的展示。"""
from datetime import date, datetime

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.outfit import Outfit, OutfitItem
from tests.conftest import make_item


@pytest.fixture
def items(user):
    return [make_item(user.id, type='上装'), make_item(user.id, type='下装'), make_item(user.id, type='外套')]


@pytest.fixture
def other_header(app, other_user):
    return {'Authorization': f'Bearer {create_access_token(identity=str(other_user.id))}'}


def _create(client, header, **payload):
    return client.post('/api/outfits', json=payload, headers=header).get_json()


def _layout(*ids):
    return [{'item_id': iid, 'x': 0.1 * i, 'y': 0.1, 'w': 0.4, 'z': i} for i, iid in enumerate(ids)]


# ---------------- 创建 ----------------
def test_create_with_name_and_collage(client, auth_header, items):
    ids = [it.id for it in items[:2]]
    body = _create(client, auth_header, item_ids=ids, name='  周一通勤  ', collage=_layout(*ids))
    assert body['code'] == 0
    data = body['data']
    assert data['name'] == '周一通勤'
    assert [it['item_id'] for it in data['items']] == ids
    assert data['item_count'] == 2
    assert [e['item_id'] for e in data['collage']] == ids


def test_create_without_name_gets_default(client, auth_header, items):
    today = date.today()
    body = _create(client, auth_header, item_ids=[items[0].id])
    assert body['data']['name'] == f'{today.month}月{today.day}日的搭配'
    assert body['data']['collage'] is None


@pytest.mark.parametrize('payload, code', [
    ({}, 3002),
    ({'item_ids': []}, 3002),
    ({'item_ids': ['x']}, 3002),
    ({'item_ids': [999]}, 3001),
    ({'item_ids': list(range(1, 14))}, 3002),
])
def test_create_bad_params(client, auth_header, payload, code):
    assert _create(client, auth_header, **payload)['code'] == code


def test_create_name_too_long(client, auth_header, items):
    assert _create(client, auth_header, item_ids=[items[0].id], name='x' * 31)['code'] == 3002


def test_create_collage_with_unselected_item(client, auth_header, items):
    body = _create(client, auth_header, item_ids=[items[0].id], collage=_layout(items[1].id))
    assert body['code'] == 3002


def test_cannot_use_others_items(client, other_header, items):
    assert _create(client, other_header, item_ids=[items[0].id])['code'] == 3001


# ---------------- 列表 ----------------
def test_list_excludes_legacy_unnamed_and_deleted(client, auth_header, user, items):
    legacy = Outfit(user_id=user.id, name=None)
    db.session.add(legacy)
    db.session.commit()

    keep = _create(client, auth_header, item_ids=[items[0].id], name='留下')['data']
    gone = _create(client, auth_header, item_ids=[items[1].id], name='删掉')['data']
    client.delete(f"/api/outfits/{gone['outfit_id']}", headers=auth_header)

    data = client.get('/api/outfits', headers=auth_header).get_json()['data']
    assert data['total'] == 1
    assert [o['outfit_id'] for o in data['list']] == [keep['outfit_id']]
    assert data['list'][0]['items'][0]['item_id'] == items[0].id


def test_list_recently_updated_first(client, auth_header, items):
    first = _create(client, auth_header, item_ids=[items[0].id], name='A')['data']
    second = _create(client, auth_header, item_ids=[items[1].id], name='B')['data']
    # 让 A 的修改时间明显更晚
    db.session.get(Outfit, first['outfit_id']).updated_at = datetime(2099, 1, 1)
    db.session.commit()

    names = [o['name'] for o in client.get('/api/outfits', headers=auth_header).get_json()['data']['list']]
    assert names == ['A', 'B']
    assert second['outfit_id']


def test_list_is_per_user(client, auth_header, other_header, items):
    _create(client, auth_header, item_ids=[items[0].id], name='我的')
    assert client.get('/api/outfits', headers=other_header).get_json()['data']['total'] == 0


def test_list_pagination(client, auth_header, items):
    for i in range(3):
        _create(client, auth_header, item_ids=[items[0].id], name=f'套{i}')
    data = client.get('/api/outfits?page=2&per_page=2', headers=auth_header).get_json()['data']
    assert data['total'] == 3 and len(data['list']) == 1


def test_deleted_item_hidden_from_outfit(client, auth_header, items):
    ids = [items[0].id, items[1].id]
    outfit = _create(client, auth_header, item_ids=ids, name='含被删衣物', collage=_layout(*ids))['data']
    client.delete(f'/api/items/{items[1].id}', headers=auth_header)

    detail = client.get(f"/api/outfits/{outfit['outfit_id']}", headers=auth_header).get_json()['data']
    assert detail['item_count'] == 1
    assert [e['item_id'] for e in detail['collage']] == [items[0].id]


# ---------------- 更新 ----------------
def test_rename(client, auth_header, items):
    outfit = _create(client, auth_header, item_ids=[items[0].id], name='旧名')['data']
    body = client.put(f"/api/outfits/{outfit['outfit_id']}", json={'name': '新名'}, headers=auth_header).get_json()
    assert body['code'] == 0 and body['data']['name'] == '新名'
    assert body['data']['item_count'] == 1


def test_rename_empty_rejected(client, auth_header, items):
    outfit = _create(client, auth_header, item_ids=[items[0].id], name='旧名')['data']
    body = client.put(f"/api/outfits/{outfit['outfit_id']}", json={'name': '  '}, headers=auth_header).get_json()
    assert body['code'] == 3002


def test_update_items_and_collage(client, auth_header, items):
    ids = [items[0].id, items[1].id]
    outfit = _create(client, auth_header, item_ids=ids, name='画布', collage=_layout(*ids))['data']
    new_ids = [items[1].id, items[2].id]
    body = client.put(f"/api/outfits/{outfit['outfit_id']}",
                      json={'item_ids': new_ids, 'collage': _layout(*new_ids)}, headers=auth_header).get_json()
    assert body['code'] == 0
    assert [it['item_id'] for it in body['data']['items']] == new_ids
    assert [e['item_id'] for e in body['data']['collage']] == new_ids
    assert OutfitItem.query.filter_by(outfit_id=outfit['outfit_id']).count() == 2


def test_update_items_only_prunes_old_collage(client, auth_header, items):
    ids = [items[0].id, items[1].id]
    outfit = _create(client, auth_header, item_ids=ids, name='画布', collage=_layout(*ids))['data']
    body = client.put(f"/api/outfits/{outfit['outfit_id']}",
                      json={'item_ids': [items[0].id]}, headers=auth_header).get_json()
    assert [e['item_id'] for e in body['data']['collage']] == [items[0].id]


def test_cannot_touch_others_outfit(client, auth_header, other_header, items):
    outfit = _create(client, auth_header, item_ids=[items[0].id], name='我的')['data']
    url = f"/api/outfits/{outfit['outfit_id']}"
    assert client.get(url, headers=other_header).get_json()['code'] == 3001
    assert client.put(url, json={'name': '抢'}, headers=other_header).get_json()['code'] == 3001
    assert client.delete(url, headers=other_header).get_json()['code'] == 3001
    assert client.get(url, headers=auth_header).get_json()['data']['name'] == '我的'


# ---------------- 删除 ----------------
def test_delete_then_not_found(client, auth_header, items):
    outfit = _create(client, auth_header, item_ids=[items[0].id], name='删')['data']
    url = f"/api/outfits/{outfit['outfit_id']}"
    assert client.delete(url, headers=auth_header).get_json()['code'] == 0
    assert client.get(url, headers=auth_header).get_json()['code'] == 3001
    assert client.delete(url, headers=auth_header).get_json()['code'] == 3001
