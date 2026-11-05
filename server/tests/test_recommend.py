# -*- coding: utf-8 -*-
"""GET /api/recommend：温度→季节、近 7 天降权、场合、配鞋、状态与归属过滤、参数校验。"""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.wear_log import WearLog
from tests.conftest import make_item


def _rec(client, header, **params):
    return client.get('/api/recommend', query_string=params, headers=header).get_json()


def _ids(combo):
    return [it['item_id'] for it in combo['items']]


def _wore(user_id, items, days_ago=0):
    db.session.add(WearLog(
        user_id=user_id,
        wear_date=date.today() - timedelta(days=days_ago),
        items_snapshot=[{'item_id': it.id} for it in items],
    ))
    db.session.commit()


# ---------------- 参数 ----------------
@pytest.mark.parametrize('params', [{}, {'temperature': 'abc'}, {'temperature': 99},
                                    {'temperature': 20, 'occasion': '约会'}])
def test_bad_params(client, auth_header, params):
    assert _rec(client, auth_header, **params)['code'] == 5002


# ---------------- 温度 → 季节 ----------------
@pytest.mark.parametrize('temp, label, season', [(5, '冬季', '冬'), (18, '春秋季', '春'), (30, '夏季', '夏')])
def test_season_band(client, auth_header, user, temp, label, season):
    top = make_item(user.id, type='上装', season=season)
    bottom = make_item(user.id, type='下装', season='全季')
    make_item(user.id, type='上装', season='冬' if season != '冬' else '夏')   # 不当季，不应出现

    data = _rec(client, auth_header, temperature=temp)['data']
    assert data['season_label'] == label
    assert data['recent_days'] == 7
    assert data['count'] == 1
    assert _ids(data['list'][0]) == [top.id, bottom.id]
    assert f'{temp}℃' in data['list'][0]['reason']


def test_dress_alone_and_max_three(client, auth_header, user):
    for _ in range(3):
        make_item(user.id, type='上装')
        make_item(user.id, type='下装')
    dress = make_item(user.id, type='连衣裙')
    data = _rec(client, auth_header, temperature=18)['data']
    assert data['count'] == 3
    assert [dress.id] in [_ids(c) for c in data['list']]


# ---------------- 近 7 天降权 ----------------
def test_recently_worn_ranked_after(client, auth_header, user):
    worn_top = make_item(user.id, type='上装', wear_count=0)
    fresh_top = make_item(user.id, type='上装', wear_count=5)   # 穿得多，但近期没穿
    bottom = make_item(user.id, type='下装')
    _wore(user.id, [worn_top], days_ago=3)

    first = _rec(client, auth_header, temperature=18)['data']['list'][0]
    assert _ids(first) == [fresh_top.id, bottom.id]
    assert '避开了近 7 天穿过的单品' in first['reason']


def test_old_wear_not_counted(client, auth_header, user):
    old_top = make_item(user.id, type='上装', wear_count=0)
    make_item(user.id, type='上装', wear_count=5)
    make_item(user.id, type='下装')
    _wore(user.id, [old_top], days_ago=7)   # 第 8 天前，不算近期

    first = _rec(client, auth_header, temperature=18)['data']['list'][0]
    assert first['items'][0]['item_id'] == old_top.id


def test_recent_still_used_when_no_alternative(client, auth_header, user):
    top = make_item(user.id, type='上装')
    bottom = make_item(user.id, type='下装')
    _wore(user.id, [top, bottom], days_ago=0)

    data = _rec(client, auth_header, temperature=18)['data']
    assert data['count'] == 1
    assert '近 7 天穿过' in data['list'][0]['reason']


def test_deleted_log_ignored(client, auth_header, user):
    from datetime import datetime
    worn = make_item(user.id, type='上装', wear_count=0)
    make_item(user.id, type='上装', wear_count=5)
    make_item(user.id, type='下装')
    _wore(user.id, [worn])
    WearLog.query.update({'deleted_at': datetime.utcnow()})
    db.session.commit()

    assert _rec(client, auth_header, temperature=18)['data']['list'][0]['items'][0]['item_id'] == worn.id


# ---------------- 场合 ----------------
def test_occasion_filter_keeps_unspecified(client, auth_header, user):
    work_top = make_item(user.id, type='上装', occasion='工作')
    make_item(user.id, type='上装', occasion='运动')
    any_bottom = make_item(user.id, type='下装', occasion=None)

    data = _rec(client, auth_header, temperature=18, occasion='工作')['data']
    assert data['occasion'] == '工作'
    assert [_ids(c) for c in data['list']] == [[work_top.id, any_bottom.id]]
    assert '工作场合' in data['list'][0]['reason']


def test_no_occasion_means_all(client, auth_header, user):
    make_item(user.id, type='上装', occasion='工作')
    make_item(user.id, type='上装', occasion='运动')
    make_item(user.id, type='下装')
    data = _rec(client, auth_header, temperature=18)['data']
    assert data['occasion'] is None
    assert data['count'] == 2


# ---------------- 外套与鞋 ----------------
def test_outer_and_shoes_added(client, auth_header, user):
    top = make_item(user.id, type='上装', season='冬')
    bottom = make_item(user.id, type='下装', season='冬')
    outer = make_item(user.id, type='外套', season='冬')
    shoes = make_item(user.id, type='鞋子', season='全季')

    combo = _rec(client, auth_header, temperature=5)['data']['list'][0]
    assert _ids(combo) == [top.id, bottom.id, outer.id, shoes.id]
    assert '配了外套和鞋子' in combo['reason']


# ---------------- 过滤 ----------------
def test_excludes_washing_deleted_and_others(client, auth_header, user, other_user):
    from datetime import datetime
    top = make_item(user.id, type='上装')
    bottom = make_item(user.id, type='下装')
    make_item(user.id, type='上装', status='洗衣中')
    make_item(user.id, type='上装', deleted_at=datetime.utcnow())
    make_item(other_user.id, type='上装')

    data = _rec(client, auth_header, temperature=18)['data']
    assert data['total_candidates'] == 2
    assert [_ids(c) for c in data['list']] == [[top.id, bottom.id]]


def test_empty_wardrobe(client, auth_header):
    data = _rec(client, auth_header, temperature=18)['data']
    assert data['count'] == 0 and data['list'] == []
