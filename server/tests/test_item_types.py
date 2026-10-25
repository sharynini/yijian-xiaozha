# -*- coding: utf-8 -*-
"""衣橱改版：新分类、场合筛选、连衣裙参与推荐。"""
import pytest

from tests.conftest import make_item


# ---------------- 新分类 ----------------
@pytest.mark.parametrize('item_type', ['连衣裙', '包包', '帽子', '外套', '上装'])
def test_create_item_with_new_types(client, auth_header, user, item_type):
    resp = client.post('/api/items', json={'image_url': '/uploads/a.jpg', 'type': item_type}, headers=auth_header)
    body = resp.get_json()

    assert body['code'] == 0
    assert body['data']['type'] == item_type


def test_reject_unknown_type(client, auth_header, user):
    resp = client.post('/api/items', json={'image_url': '/uploads/a.jpg', 'type': '袜子'}, headers=auth_header)
    assert resp.get_json()['code'] == 2002


# ---------------- 场合筛选 ----------------
def test_filter_by_occasion(client, auth_header, user):
    make_item(user.id, occasion='工作')
    make_item(user.id, occasion='运动')
    make_item(user.id, occasion=None)

    data = client.get('/api/items', query_string={'occasion': '工作'}, headers=auth_header).get_json()['data']
    assert data['total'] == 1
    assert data['list'][0]['occasion'] == '工作'


def test_filters_combine_with_and(client, auth_header, user):
    make_item(user.id, type='连衣裙', season='夏', occasion='日常')
    make_item(user.id, type='连衣裙', season='冬', occasion='日常')
    make_item(user.id, type='上装', season='夏', occasion='日常')

    data = client.get(
        '/api/items', query_string={'type': '连衣裙', 'season': '夏', 'occasion': '日常'}, headers=auth_header
    ).get_json()['data']
    assert data['total'] == 1


# ---------------- 推荐 ----------------
def _recommend(client, auth_header, temperature=20):
    return client.get('/api/recommend', query_string={'temperature': temperature}, headers=auth_header).get_json()['data']


def test_recommend_dress_only(client, auth_header, user):
    """只有连衣裙也能生成推荐（以前必须同时有上装和下装）"""
    make_item(user.id, type='连衣裙', season='春')

    data = _recommend(client, auth_header)
    assert data['count'] == 1
    assert [it['type'] for it in data['list'][0]['items']] == ['连衣裙']


def test_recommend_mixes_pairs_and_dresses(client, auth_header, user):
    make_item(user.id, type='上装', season='春')
    make_item(user.id, type='下装', season='春')
    make_item(user.id, type='连衣裙', season='全季')

    data = _recommend(client, auth_header)
    combos = [sorted(it['type'] for it in c['items']) for c in data['list']]
    assert sorted(['上装', '下装']) in combos
    assert ['连衣裙'] in combos


def test_recommend_dress_with_outer(client, auth_header, user):
    make_item(user.id, type='连衣裙', season='冬')
    make_item(user.id, type='外套', season='冬')

    data = _recommend(client, auth_header, temperature=5)
    assert sorted(it['type'] for it in data['list'][0]['items']) == ['外套', '连衣裙']
