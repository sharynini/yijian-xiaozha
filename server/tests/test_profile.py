# -*- coding: utf-8 -*-
"""PUT /api/auth/profile：改昵称、改头像（只能是本人上传的图片）、参数校验、只改自己、需登录。"""
import pytest
from flask_jwt_extended import create_access_token


@pytest.fixture
def folder(app, tmp_path):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    return tmp_path


def _put(client, header, **payload):
    return client.put('/api/auth/profile', json=payload, headers=header)


def test_update_nickname(client, auth_header):
    body = _put(client, auth_header, nickname='  桃桃的主人  ').get_json()
    assert body['code'] == 0
    assert body['data']['nickname'] == '桃桃的主人'
    assert client.get('/api/auth/profile', headers=auth_header).get_json()['data']['nickname'] == '桃桃的主人'


@pytest.mark.parametrize('nickname', ['', '   ', None, 123, 'x' * 21])
def test_bad_nickname(client, auth_header, nickname):
    assert _put(client, auth_header, nickname=nickname).get_json()['code'] == 1004


def test_nickname_max_length_ok(client, auth_header):
    assert _put(client, auth_header, nickname='衣' * 20).get_json()['code'] == 0


def test_update_avatar_with_url_or_path(client, auth_header, user, folder):
    (folder / f'{user.id}_a.png').write_bytes(b'x')
    body = _put(client, auth_header, avatar=f'http://localhost/uploads/{user.id}_a.png').get_json()
    assert body['code'] == 0
    assert body['data']['avatar'].endswith(f'/uploads/{user.id}_a.png')

    (folder / f'{user.id}_b.jpg').write_bytes(b'x')
    body = _put(client, auth_header, avatar=f'/uploads/{user.id}_b.jpg').get_json()
    assert body['data']['avatar'].endswith(f'/uploads/{user.id}_b.jpg')


@pytest.mark.parametrize('avatar', [
    'https://cdn.example.com/uploads/1_a.png',   # 外部链接
    '/uploads/../config.py',                      # 目录穿越
    '',
    None,
])
def test_bad_avatar(client, auth_header, folder, avatar):
    assert _put(client, auth_header, avatar=avatar).get_json()['code'] == 1004


def test_avatar_must_be_own_and_exist(client, auth_header, user, other_user, folder):
    (folder / f'{other_user.id}_x.png').write_bytes(b'x')
    assert _put(client, auth_header, avatar=f'/uploads/{other_user.id}_x.png').get_json()['code'] == 1004
    assert _put(client, auth_header, avatar=f'/uploads/{user.id}_missing.png').get_json()['code'] == 1004
    (folder / f'{user.id}_doc.txt').write_bytes(b'x')
    assert _put(client, auth_header, avatar=f'/uploads/{user.id}_doc.txt').get_json()['code'] == 1004


def test_partial_update_keeps_other_field(client, auth_header, user, folder):
    (folder / f'{user.id}_a.png').write_bytes(b'x')
    _put(client, auth_header, avatar=f'/uploads/{user.id}_a.png')
    body = _put(client, auth_header, nickname='新名字').get_json()
    assert body['data']['avatar'].endswith(f'/uploads/{user.id}_a.png')
    assert body['data']['nickname'] == '新名字'


def test_only_changes_own_profile(app, client, auth_header, other_user):
    _put(client, auth_header, nickname='我自己')
    other_header = {'Authorization': f'Bearer {create_access_token(identity=str(other_user.id))}'}
    assert client.get('/api/auth/profile', headers=other_header).get_json()['data']['nickname'] == 'bob'


def test_requires_login(client):
    assert client.put('/api/auth/profile', json={'nickname': 'x'}).status_code == 401
