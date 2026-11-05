# -*- coding: utf-8 -*-
"""GET /api/wear-logs：倒序分页、按日期筛选、日期格式、用户隔离、软删除过滤。"""
from datetime import date, datetime

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.wear_log import WearLog


def _log(user_id, day, deleted=False):
    log = WearLog(user_id=user_id, wear_date=day, items_snapshot=[],
                  deleted_at=datetime.utcnow() if deleted else None)
    db.session.add(log)
    db.session.commit()
    return log


def _list(client, header, **params):
    return client.get('/api/wear-logs', query_string=params, headers=header).get_json()


@pytest.fixture
def logs(user):
    """三个日期，其中 11-05 有两条（后建的排前面）"""
    a = _log(user.id, date(2026, 10, 28))
    b = _log(user.id, date(2026, 11, 3))
    c1 = _log(user.id, date(2026, 11, 5))
    c2 = _log(user.id, date(2026, 11, 5))
    return {'a': a.id, 'b': b.id, 'c1': c1.id, 'c2': c2.id}


def test_desc_order_and_pagination(client, auth_header, logs):
    data = _list(client, auth_header, page=1, per_page=3)['data']
    assert data['total'] == 4
    assert [x['log_id'] for x in data['list']] == [logs['c2'], logs['c1'], logs['b']]
    data2 = _list(client, auth_header, page=2, per_page=3)['data']
    assert [x['log_id'] for x in data2['list']] == [logs['a']]


def test_filter_by_date(client, auth_header, logs):
    data = _list(client, auth_header, date='2026-11-05')['data']
    assert data['total'] == 2
    assert [x['log_id'] for x in data['list']] == [logs['c2'], logs['c1']]
    assert {x['wear_date'] for x in data['list']} == {'2026-11-05'}


def test_filter_date_without_logs(client, auth_header, logs):
    data = _list(client, auth_header, date='2026-11-04')['data']
    assert data['total'] == 0 and data['list'] == []


def test_empty_date_means_all(client, auth_header, logs):
    assert _list(client, auth_header, date='')['data']['total'] == 4


@pytest.mark.parametrize('bad', ['2026/11/05', '2026-13-01', 'abc', '20261105'])
def test_bad_date(client, auth_header, logs, bad):
    assert _list(client, auth_header, date=bad)['code'] == 4002


def test_only_own_and_not_deleted(app, client, auth_header, user, other_user, logs):
    _log(other_user.id, date(2026, 11, 5))
    _log(user.id, date(2026, 11, 5), deleted=True)
    data = _list(client, auth_header, date='2026-11-05')['data']
    assert data['total'] == 2

    other_header = {'Authorization': f'Bearer {create_access_token(identity=str(other_user.id))}'}
    assert _list(client, other_header, date='2026-11-05')['data']['total'] == 1
