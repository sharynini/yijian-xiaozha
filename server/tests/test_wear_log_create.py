# -*- coding: utf-8 -*-
"""POST /api/wear-logs：item_ids 主路径与事务。"""
from datetime import datetime
from unittest.mock import patch

from app.extensions import db
from app.models.item import Item
from app.models.wear_log import WearLog
from app.modules.wear_log.services import WearLogService
from tests.conftest import make_item


def _post(client, auth_header, payload):
    return client.post('/api/wear-logs', json=payload, headers=auth_header)


def test_create_with_item_ids_success(client, auth_header, user):
    first = make_item(user.id, type='上装')
    second = make_item(user.id, type='下装', image_url='https://example.com/b.jpg')

    resp = _post(client, auth_header, {
        'item_ids': [first.id, second.id, first.id],
        'mood': '开心',
        'increase_wear_count': False,
    })
    body = resp.get_json()

    assert resp.status_code == 200
    assert body['code'] == 0
    data = body['data']
    assert data['outfit_id'] is None
    assert data['mood'] == '开心'
    assert [it['item_id'] for it in data['items']] == [first.id, second.id]
    assert data['items'][0]['type'] == '上装'
    assert WearLog.query.filter_by(user_id=user.id).count() == 1


def test_reject_other_users_item(client, auth_header, user, other_user):
    mine = make_item(user.id)
    theirs = make_item(other_user.id, image_url='https://example.com/other.jpg')

    resp = _post(client, auth_header, {'item_ids': [mine.id, theirs.id]})
    body = resp.get_json()

    assert body['code'] == 4003
    assert '不属于当前用户' in body['msg']
    assert WearLog.query.count() == 0


def test_reject_deleted_item(client, auth_header, user):
    alive = make_item(user.id)
    gone = make_item(user.id, image_url='https://example.com/gone.jpg')
    gone.deleted_at = datetime.utcnow()
    db.session.commit()

    resp = _post(client, auth_header, {'item_ids': [alive.id, gone.id]})
    body = resp.get_json()

    assert body['code'] == 4004
    assert '已删除' in body['msg']
    assert WearLog.query.count() == 0


def test_reject_empty_item_ids(client, auth_header):
    resp = _post(client, auth_header, {'item_ids': []})
    body = resp.get_json()

    assert body['code'] == 4002
    assert '空数组' in body['msg']
    assert WearLog.query.count() == 0


def test_reject_more_than_12_items(client, auth_header, user):
    ids = [make_item(user.id, image_url=f'https://example.com/{i}.jpg').id for i in range(13)]
    resp = _post(client, auth_header, {'item_ids': ids})
    body = resp.get_json()

    assert body['code'] == 4002
    assert '12' in body['msg']
    assert WearLog.query.count() == 0


def test_increase_wear_count(client, auth_header, user):
    first = make_item(user.id, wear_count=3)
    second = make_item(user.id, wear_count=1, image_url='https://example.com/b.jpg')

    resp = _post(client, auth_header, {
        'item_ids': [first.id, second.id],
        'increase_wear_count': True,
    })
    assert resp.get_json()['code'] == 0

    db.session.expire_all()
    assert db.session.get(Item, first.id).wear_count == 4
    assert db.session.get(Item, second.id).wear_count == 2


def test_transaction_rollback_on_commit_failure(app, user):
    item = make_item(user.id, wear_count=5)
    before_logs = WearLog.query.count()

    with patch.object(db.session, 'commit', side_effect=RuntimeError('db fail')):
        raised = False
        try:
            WearLogService.create(user.id, {
                'item_ids': [item.id],
                'increase_wear_count': True,
            })
        except RuntimeError:
            raised = True

    assert raised
    db.session.expire_all()
    assert WearLog.query.count() == before_logs
    assert db.session.get(Item, item.id).wear_count == 5
