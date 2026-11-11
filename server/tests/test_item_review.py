# -*- coding: utf-8 -*-
"""批量上传支持：衣物「待确认」标记 needs_review 与内部类别「未分类」。"""
from tests.conftest import make_item


def _create(client, header, **body):
    payload = {'image_url': '/uploads/a.jpg', 'type': '上装'}
    payload.update(body)
    return client.post('/api/items', json=payload, headers=header).get_json()


def _update(client, header, item_id, **body):
    return client.put(f'/api/items/{item_id}', json=body, headers=header).get_json()


# ---------------- 新增 ----------------
def test_default_is_not_pending(client, auth_header):
    body = _create(client, auth_header)
    assert body['code'] == 0
    assert body['data']['needs_review'] is False


def test_batch_item_can_be_saved_as_pending(client, auth_header):
    body = _create(client, auth_header, type='连衣裙', color='黑色', needs_review=True)
    assert body['code'] == 0
    assert body['data']['needs_review'] is True


def test_unclassified_allowed_only_when_pending(client, auth_header):
    ok = _create(client, auth_header, type='未分类', needs_review=True)
    assert ok['code'] == 0 and ok['data']['type'] == '未分类'

    rejected = _create(client, auth_header, type='未分类')
    assert rejected['code'] == 2003


def test_bad_needs_review_value(client, auth_header):
    assert _create(client, auth_header, needs_review='maybe')['code'] == 2002


# ---------------- 确认 ----------------
def test_cannot_confirm_while_unclassified(client, auth_header):
    item_id = _create(client, auth_header, type='未分类', needs_review=True)['data']['item_id']

    body = _update(client, auth_header, item_id, needs_review=False)
    assert body['code'] == 2003

    # 被拒后数据保持原样
    detail = client.get(f'/api/items/{item_id}', headers=auth_header).get_json()['data']
    assert detail['needs_review'] is True and detail['type'] == '未分类'


def test_confirm_after_choosing_type(client, auth_header):
    item_id = _create(client, auth_header, type='未分类', needs_review=True)['data']['item_id']
    body = _update(client, auth_header, item_id, type='外套', season='冬', needs_review=False)
    assert body['code'] == 0
    assert body['data']['type'] == '外套' and body['data']['needs_review'] is False


def test_editing_other_fields_keeps_pending(client, auth_header):
    item_id = _create(client, auth_header, type='未分类', needs_review=True)['data']['item_id']
    body = _update(client, auth_header, item_id, remark='妈妈送的')
    assert body['code'] == 0 and body['data']['needs_review'] is True


# ---------------- 列表 ----------------
def test_list_filter_and_pending_count(client, auth_header, user, other_user):
    make_item(user.id, needs_review=True)
    make_item(user.id, type='未分类', needs_review=True)
    make_item(user.id)
    make_item(other_user.id, needs_review=True)   # 别人的不计入

    data = client.get('/api/items', headers=auth_header).get_json()['data']
    assert data['total'] == 3 and data['pending_review'] == 2

    pending = client.get('/api/items', query_string={'needs_review': 1}, headers=auth_header).get_json()['data']
    assert pending['total'] == 2 and all(it['needs_review'] for it in pending['list'])

    confirmed = client.get('/api/items', query_string={'needs_review': 'false'}, headers=auth_header).get_json()['data']
    assert confirmed['total'] == 1 and confirmed['pending_review'] == 2


# ---------------- 推荐 ----------------
def test_recommend_skips_unclassified_but_keeps_pending(client, auth_header, user):
    make_item(user.id, type='未分类', needs_review=True)
    top = make_item(user.id, type='上装', needs_review=True)   # 已识别出类别、只是未核对：照常推荐
    bottom = make_item(user.id, type='下装')

    data = client.get('/api/recommend', query_string={'temperature': 18}, headers=auth_header).get_json()['data']
    assert data['total_candidates'] == 2
    assert [it['item_id'] for it in data['list'][0]['items']] == [top.id, bottom.id]
