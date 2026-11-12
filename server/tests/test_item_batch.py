# -*- coding: utf-8 -*-
"""衣橱多选：批量删除、撤销、删除影响预估、批量确认。"""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.item import Item
from app.models.outfit import Outfit, OutfitItem
from tests.conftest import make_item


def _post(client, header, path, ids):
    return client.post(f'/api/items/{path}', json={'ids': ids}, headers=header).get_json()


def _make_outfit(user_id, item_ids, deleted=False):
    outfit = Outfit(user_id=user_id, name='测试搭配', deleted_at=datetime.utcnow() if deleted else None)
    db.session.add(outfit)
    db.session.flush()
    for iid in item_ids:
        db.session.add(OutfitItem(outfit_id=outfit.id, item_id=iid))
    db.session.commit()
    return outfit


# ---------------- 参数校验（四个接口共用） ----------------
@pytest.mark.parametrize('path', ['batch-delete', 'restore', 'delete-impact', 'batch-confirm'])
@pytest.mark.parametrize('ids', [None, [], 'abc', [0], [-1], ['x'], [True], [{'id': 1}], list(range(1, 102))])
def test_bad_ids(client, auth_header, path, ids):
    assert _post(client, auth_header, path, ids)['code'] == 2002


def test_requires_login(client):
    assert client.post('/api/items/batch-delete', json={'ids': [1]}).status_code == 401


# ---------------- 批量删除 ----------------
def test_batch_delete_only_own_and_alive(client, auth_header, user, other_user):
    a, b = make_item(user.id), make_item(user.id)
    keep = make_item(user.id)
    gone = make_item(user.id, deleted_at=datetime.utcnow())
    foreign = make_item(other_user.id)

    body = _post(client, auth_header, 'batch-delete', [a.id, b.id, gone.id, foreign.id, 99999, a.id])
    assert body['code'] == 0
    assert sorted(body['data']['deleted']) == sorted([a.id, b.id])

    listing = client.get('/api/items', headers=auth_header).get_json()['data']
    assert [it['item_id'] for it in listing['list']] == [keep.id]
    assert db.session.get(Item, foreign.id).deleted_at is None   # 别人的不受影响


def test_ids_as_strings_are_accepted(client, auth_header, user):
    a = make_item(user.id)
    assert _post(client, auth_header, 'batch-delete', [str(a.id)])['data']['deleted'] == [a.id]


# ---------------- 撤销 ----------------
def test_restore_after_batch_delete(client, auth_header, user):
    a, b = make_item(user.id), make_item(user.id)
    _post(client, auth_header, 'batch-delete', [a.id, b.id])

    body = _post(client, auth_header, 'restore', [a.id, b.id])
    assert body['code'] == 0 and sorted(body['data']['restored']) == sorted([a.id, b.id])
    assert client.get('/api/items', headers=auth_header).get_json()['data']['total'] == 2


def test_restore_window_and_ownership(client, auth_header, user, other_user):
    old = make_item(user.id, deleted_at=datetime.utcnow() - timedelta(hours=1))   # 超过撤销时限
    foreign = make_item(other_user.id, deleted_at=datetime.utcnow())             # 别人的
    alive = make_item(user.id)                                                    # 没删除的

    body = _post(client, auth_header, 'restore', [old.id, foreign.id, alive.id])
    assert body['code'] == 0 and body['data']['restored'] == []
    assert db.session.get(Item, old.id).deleted_at is not None
    assert db.session.get(Item, foreign.id).deleted_at is not None


# ---------------- 删除影响预估 ----------------
def test_delete_impact_counts_saved_outfits(client, auth_header, user):
    top, bottom, shoes, lonely = (make_item(user.id) for _ in range(4))
    _make_outfit(user.id, [top.id, bottom.id])
    _make_outfit(user.id, [top.id, shoes.id])
    _make_outfit(user.id, [bottom.id], deleted=True)     # 已删除的搭配不算

    data = _post(client, auth_header, 'delete-impact', [top.id, bottom.id, lonely.id])['data']
    assert data == {'items_in_outfits': 2, 'outfits': 2}
    assert _post(client, auth_header, 'delete-impact', [lonely.id])['data'] == {'items_in_outfits': 0, 'outfits': 0}


def test_delete_impact_ignores_other_users_items(client, auth_header, other_user):
    foreign = make_item(other_user.id)
    _make_outfit(other_user.id, [foreign.id])
    assert _post(client, auth_header, 'delete-impact', [foreign.id])['data'] == {'items_in_outfits': 0, 'outfits': 0}


# ---------------- 批量确认 ----------------
def test_batch_confirm_skips_unclassified(client, auth_header, user, other_user):
    ok1 = make_item(user.id, type='上装', needs_review=True)
    ok2 = make_item(user.id, type='鞋子', needs_review=True)
    unknown = make_item(user.id, type='未分类', needs_review=True)
    already = make_item(user.id, type='下装')
    foreign = make_item(other_user.id, type='上装', needs_review=True)

    body = _post(client, auth_header, 'batch-confirm', [ok1.id, ok2.id, unknown.id, already.id, foreign.id])
    assert body['code'] == 0
    assert sorted(body['data']['confirmed']) == sorted([ok1.id, ok2.id])
    assert body['data']['skipped_unclassified'] == [unknown.id]

    listing = client.get('/api/items', headers=auth_header).get_json()['data']
    assert listing['pending_review'] == 1
    assert db.session.get(Item, foreign.id).needs_review is True
