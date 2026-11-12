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


# ---------------- 端到端：模拟前端批量添加 → 核对的完整请求 ----------------
def _confirm_payload(**overrides):
    """与 client/src/pages/item/add.vue 的 submit() 发出的字段完全一致（空字段是空串 / null）"""
    payload = {
        'image_url': '/uploads/a_cutout.png', 'type': '', 'color': '', 'season': '',
        'occasion': '', 'material': '', 'brand': '', 'price': None, 'remark': '',
        'needs_review': False,
    }
    payload.update(overrides)
    return payload


def test_batch_then_review_flow(client, auth_header):
    # 1. 批量页：一张识别成功、一张识别失败（存「未分类」）
    recognized = _create(client, auth_header, image_url='/uploads/a_cutout.png', type='上装',
                         color='白色', season='夏', needs_review=True)['data']
    unknown = _create(client, auth_header, image_url='/uploads/b.jpg', type='未分类',
                      needs_review=True)['data']

    listing = client.get('/api/items', headers=auth_header).get_json()['data']
    assert listing['pending_review'] == 2

    # 2. 核对识别成功的：改一下颜色、加备注后确认
    body = _update(client, auth_header, recognized['item_id'],
                   **_confirm_payload(type='上装', color='米色', season='夏', remark='通勤穿'))
    assert body['code'] == 0
    assert body['data']['needs_review'] is False
    assert body['data']['color'] == '米色' and body['data']['remark'] == '通勤穿'

    # 3. 「未分类」那件：前端会清空类别，没选就提交 → 后端拒绝（类型不能为空）
    assert _update(client, auth_header, unknown['item_id'], **_confirm_payload())['code'] == 2002

    # 选好类别后确认成功
    body = _update(client, auth_header, unknown['item_id'],
                   **_confirm_payload(image_url='/uploads/b.jpg', type='鞋子', season='全季'))
    assert body['code'] == 0 and body['data']['type'] == '鞋子'

    # 4. 都核对完：待确认清零，待确认列表为空
    listing = client.get('/api/items', headers=auth_header).get_json()['data']
    assert listing['pending_review'] == 0 and listing['total'] == 2
    pending = client.get('/api/items', query_string={'needs_review': 1}, headers=auth_header).get_json()['data']
    assert pending['total'] == 0


def test_other_user_cannot_confirm(client, auth_header, other_user):
    foreign = make_item(other_user.id, type='未分类', needs_review=True)
    body = _update(client, auth_header, foreign.id, **_confirm_payload(type='上装', season='夏'))
    assert body['code'] == 2001
