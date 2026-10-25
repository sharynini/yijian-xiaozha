# -*- coding: utf-8 -*-
"""手动搭配画布：POST /api/wear-logs 的 collage 字段。"""
from app.extensions import db
from app.models.wear_log import WearLog
from tests.conftest import make_item


def _post(client, auth_header, payload):
    return client.post('/api/wear-logs', json=payload, headers=auth_header).get_json()


def test_collage_saved_and_returned(client, auth_header, user):
    top = make_item(user.id, type='上装')
    bottom = make_item(user.id, type='下装')

    body = _post(client, auth_header, {
        'item_ids': [top.id, bottom.id],
        'mood': '开心',
        'collage': [
            {'item_id': top.id, 'x': 0.1, 'y': 0.05, 'w': 0.5, 'z': 1},
            {'item_id': bottom.id, 'x': 0.3, 'y': 0.5, 'w': 0.45, 'z': 2},
        ],
    })

    assert body['code'] == 0
    assert body['data']['collage'][1] == {'item_id': bottom.id, 'x': 0.3, 'y': 0.5, 'w': 0.45, 'z': 2}
    assert db.session.get(WearLog, body['data']['log_id']).collage[0]['item_id'] == top.id


def test_collage_optional(client, auth_header, user):
    item = make_item(user.id)
    body = _post(client, auth_header, {'item_ids': [item.id]})
    assert body['code'] == 0
    assert body['data']['collage'] is None


def test_collage_values_clamped(client, auth_header, user):
    item = make_item(user.id)
    body = _post(client, auth_header, {
        'item_ids': [item.id],
        'collage': [{'item_id': item.id, 'x': -1, 'y': 3, 'w': 0.001, 'z': 500}],
    })
    assert body['data']['collage'][0] == {'item_id': item.id, 'x': 0.0, 'y': 1.0, 'w': 0.05, 'z': 99}


def test_collage_rejects_unselected_item(client, auth_header, user):
    chosen = make_item(user.id)
    other = make_item(user.id)
    body = _post(client, auth_header, {
        'item_ids': [chosen.id],
        'collage': [{'item_id': other.id, 'x': 0, 'y': 0, 'w': 0.3}],
    })
    assert body['code'] == 4005
    assert WearLog.query.count() == 0


def test_collage_rejects_bad_shape(client, auth_header, user):
    item = make_item(user.id)
    body = _post(client, auth_header, {'item_ids': [item.id], 'collage': 'oops'})
    assert body['code'] == 4005
