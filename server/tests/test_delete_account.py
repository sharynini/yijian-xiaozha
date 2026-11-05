# -*- coding: utf-8 -*-
"""DELETE /api/auth/account：彻底删除本人数据与图片、不误删他人、旧 token 失效。"""
import os
from datetime import datetime

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.item import Item
from app.models.outfit import Outfit, OutfitItem
from app.models.user import User
from app.models.wear_log import WearLog
from tests.conftest import make_item


@pytest.fixture
def upload_dir(app, tmp_path):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    return tmp_path


def _seed(user_id):
    """给用户造一份完整数据：2 件衣物、1 套搭配、1 条日记"""
    top = make_item(user_id, image_url=f'/uploads/{user_id}_top.jpg')
    bottom = make_item(user_id, type='下装', image_url=f'/uploads/{user_id}_bottom.png')
    outfit = Outfit(user_id=user_id, name='周一')
    db.session.add(outfit)
    db.session.flush()
    db.session.add_all([OutfitItem(outfit_id=outfit.id, item_id=top.id),
                        OutfitItem(outfit_id=outfit.id, item_id=bottom.id)])
    db.session.add(WearLog(user_id=user_id, wear_date=datetime.utcnow().date(),
                           items_snapshot=[{'item_id': top.id}], photo_url=f'/uploads/{user_id}_photo.jpg'))
    db.session.commit()


def _touch(folder, *names):
    for name in names:
        (folder / name).write_bytes(b'x')


def test_delete_removes_all_own_data_and_files(app, client, user, other_user, auth_header, upload_dir):
    _seed(user.id)
    _seed(other_user.id)
    _touch(upload_dir, f'{user.id}_top.jpg', f'{user.id}_bottom.png', f'{user.id}_photo.jpg',
           f'{other_user.id}_top.jpg', f'{other_user.id}_photo.jpg', 'readme.txt')
    user_id, other_id = user.id, other_user.id

    body = client.delete('/api/auth/account', headers=auth_header).get_json()
    assert body['code'] == 0
    assert body['data']['deleted_files'] == 3

    assert db.session.get(User, user_id) is None
    assert Item.query.filter_by(user_id=user_id).count() == 0
    assert Outfit.query.filter_by(user_id=user_id).count() == 0
    assert WearLog.query.filter_by(user_id=user_id).count() == 0

    # 他人数据与文件原样保留
    assert db.session.get(User, other_id) is not None
    assert Item.query.filter_by(user_id=other_id).count() == 2
    assert Outfit.query.filter_by(user_id=other_id).count() == 1
    assert OutfitItem.query.count() == 2
    assert WearLog.query.filter_by(user_id=other_id).count() == 1
    assert sorted(os.listdir(upload_dir)) == sorted([f'{other_id}_top.jpg', f'{other_id}_photo.jpg', 'readme.txt'])


def test_prefix_does_not_match_longer_user_id(app, client, user, auth_header, upload_dir):
    """用户 1 注销不能删掉用户 11 的文件（前缀是 '1_' 而不是 '1'）"""
    _touch(upload_dir, f'{user.id}_a.jpg', f'{user.id}1_b.jpg')
    client.delete('/api/auth/account', headers=auth_header)
    assert os.listdir(upload_dir) == [f'{user.id}1_b.jpg']


def test_old_token_invalid_after_delete(client, auth_header, upload_dir):
    assert client.delete('/api/auth/account', headers=auth_header).get_json()['code'] == 0

    for resp in (
        client.get('/api/auth/profile', headers=auth_header),
        client.get('/api/items', headers=auth_header),
        client.delete('/api/auth/account', headers=auth_header),
    ):
        assert resp.status_code == 401


def test_soft_deleted_user_token_invalid(client, user, auth_header):
    user.deleted_at = datetime.utcnow()
    db.session.commit()
    assert client.get('/api/items', headers=auth_header).status_code == 401


def test_requires_login(client):
    assert client.delete('/api/auth/account').status_code == 401


def test_same_username_can_register_again(client, user, auth_header, upload_dir):
    client.delete('/api/auth/account', headers=auth_header)
    body = client.post('/api/auth/register',
                       json={'username': 'alice', 'email': 'alice@example.com', 'password': 'secret1'}).get_json()
    assert body['code'] == 0


def test_works_with_no_upload_folder(app, client, auth_header, tmp_path):
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'missing')
    body = client.delete('/api/auth/account', headers=auth_header).get_json()
    assert body['code'] == 0
    assert body['data']['deleted_files'] == 0


def test_other_users_token_still_valid(app, client, user, other_user, auth_header, upload_dir):
    other_header = {'Authorization': f'Bearer {create_access_token(identity=str(other_user.id))}'}
    client.delete('/api/auth/account', headers=auth_header)
    assert client.get('/api/auth/profile', headers=other_header).get_json()['code'] == 0
