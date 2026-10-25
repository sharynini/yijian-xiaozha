# -*- coding: utf-8 -*-
"""POST /api/ai/recognize-item：不会真的调用模型，用 mock 代替。"""
from unittest.mock import patch

import pytest

from app.modules.ai import services as ai_services

URL = '/api/ai/recognize-item'


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    ai_services._calls.clear()
    yield
    ai_services._calls.clear()


@pytest.fixture
def configured(app, tmp_path):
    app.config['DASHSCOPE_API_KEY'] = 'test-key'
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    return tmp_path


def _own_image(folder, user_id, name='abc.jpg'):
    filename = f'{user_id}_{name}'
    (folder / filename).write_bytes(b'fake-image-bytes')
    return f'/uploads/{filename}'


def _post(client, auth_header, image_url):
    return client.post(URL, json={'image_url': image_url}, headers=auth_header).get_json()


def _mock_model(reply):
    return patch.object(ai_services.AiService, '_call_model', return_value=reply)


# ---------------- 正常识别 ----------------
def test_recognize_success(client, auth_header, user, configured):
    image = _own_image(configured, user.id)
    reply = '{"type":"连衣裙","color":"粉色","season":"夏","occasion":"日常"}'

    with _mock_model(reply) as mocked:
        body = _post(client, auth_header, image)

    assert body['code'] == 0
    assert body['data'] == {'type': '连衣裙', 'color': '粉色', 'season': '夏', 'occasion': '日常'}
    # 传给模型的是 base64 data URL，不是本地地址
    assert mocked.call_args[0][1].startswith('data:image/jpeg;base64,')


def test_accepts_absolute_url(client, auth_header, user, configured):
    """前端传的是上传接口返回的完整地址，也要能识别"""
    image = 'http://localhost' + _own_image(configured, user.id)
    with _mock_model('{"type":"上装","color":"白色","season":"春","occasion":"工作"}'):
        assert _post(client, auth_header, image)['code'] == 0


def test_reply_wrapped_in_markdown(client, auth_header, user, configured):
    image = _own_image(configured, user.id)
    reply = '好的，识别结果如下：\n```json\n{"type":"外套","color":"黑色","season":"冬","occasion":"正式"}\n```'
    with _mock_model(reply):
        assert _post(client, auth_header, image)['data']['type'] == '外套'


def test_invalid_values_dropped(client, auth_header, user, configured):
    """模型乱写的值不会传给前端"""
    image = _own_image(configured, user.id)
    reply = '{"type":"T恤","color":"白色","season":"初夏","occasion":null}'
    with _mock_model(reply):
        data = _post(client, auth_header, image)['data']
    assert data == {'type': None, 'color': '白色', 'season': None, 'occasion': None}


def test_nothing_recognized(client, auth_header, user, configured):
    image = _own_image(configured, user.id)
    with _mock_model('这张图片里没有衣服'):
        assert _post(client, auth_header, image)['code'] == 8003
    with _mock_model('{"type":null,"color":null,"season":null,"occasion":null}'):
        assert _post(client, auth_header, image)['code'] == 8003


# ---------------- 配置与权限 ----------------
def test_not_configured(app, client, auth_header, user, tmp_path):
    app.config['DASHSCOPE_API_KEY'] = ''
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    image = _own_image(tmp_path, user.id)
    assert _post(client, auth_header, image)['code'] == 8001


def test_reject_other_users_image(client, auth_header, user, other_user, configured):
    image = _own_image(configured, other_user.id)
    with _mock_model('{}') as mocked:
        assert _post(client, auth_header, image)['code'] == 8002
    mocked.assert_not_called()


@pytest.mark.parametrize('image_url', [
    'https://cdn.example.com/uploads/1_a.jpg',
    '/uploads/../config.py',
    '/uploads/1_missing.jpg',
    '',
    None,
])
def test_reject_bad_image(client, auth_header, user, configured, image_url):
    with _mock_model('{}') as mocked:
        assert _post(client, auth_header, image_url)['code'] == 8002
    mocked.assert_not_called()


def test_rate_limit(client, auth_header, user, configured):
    image = _own_image(configured, user.id)
    with _mock_model('{"type":"上装","color":null,"season":null,"occasion":null}'):
        for _ in range(ai_services.RATE_LIMIT):
            assert _post(client, auth_header, image)['code'] == 0
        assert _post(client, auth_header, image)['code'] == 8004
