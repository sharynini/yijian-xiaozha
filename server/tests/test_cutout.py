# -*- coding: utf-8 -*-
"""POST /api/ai/cutout：用假的去背景函数代替 rembg，不需要下载模型。"""
from unittest.mock import patch

import pytest
from PIL import Image

from app.common.errors import ApiError
from app.modules.ai import services as ai_services

URL = '/api/ai/cutout'


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    ai_services._cutout_calls.clear()
    ai_services._cutout_daily_calls.clear()
    yield
    ai_services._cutout_calls.clear()
    ai_services._cutout_daily_calls.clear()


@pytest.fixture
def folder(app, tmp_path):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    return tmp_path


def _own_photo(folder, user_id, name='photo.jpg', size=(400, 300)):
    filename = f'{user_id}_{name}'
    Image.new('RGB', size, (200, 180, 150)).save(folder / filename, 'JPEG')
    return f'/uploads/{filename}'


def _fake_cutout(image):
    """模拟 rembg：中间一块不透明（衣服），四周透明（背景）"""
    out = Image.new('RGBA', image.size, (0, 0, 0, 0))
    w, h = image.size
    out.paste(Image.new('RGBA', (w // 4, h // 2), (255, 0, 0, 255)), (w // 4, h // 4))
    return out


def _post(client, auth_header, image_url):
    return client.post(URL, json={'image_url': image_url}, headers=auth_header).get_json()


def test_cutout_success(client, auth_header, user, folder):
    image = _own_photo(folder, user.id)
    with patch.object(ai_services.CutoutService, '_remove_background', side_effect=_fake_cutout):
        body = _post(client, auth_header, image)

    assert body['code'] == 0
    path = body['data']['path']
    assert path.startswith(f'/uploads/{user.id}_') and path.endswith('.png')
    assert body['data']['url'] == 'http://localhost' + path

    saved = Image.open(folder / path.rsplit('/', 1)[-1])
    assert saved.mode == 'RGBA'
    # 四周透明部分被裁掉，只留中间衣服（加少量边距）
    assert saved.size[0] < 400 and saved.size[1] < 300
    # 原图仍在磁盘上
    assert (folder / f'{user.id}_photo.jpg').exists()


def test_large_image_is_downscaled(app, client, auth_header, user, folder):
    app.config['CUTOUT_MAX_SIDE'] = 200
    image = _own_photo(folder, user.id, size=(1600, 800))
    seen = {}

    def fake(img):
        seen['size'] = img.size
        return _fake_cutout(img)

    with patch.object(ai_services.CutoutService, '_remove_background', side_effect=fake):
        assert _post(client, auth_header, image)['code'] == 0
    assert max(seen['size']) == 200


def test_nothing_found(client, auth_header, user, folder):
    image = _own_photo(folder, user.id)
    blank = lambda img: Image.new('RGBA', img.size, (0, 0, 0, 0))  # noqa: E731
    with patch.object(ai_services.CutoutService, '_remove_background', side_effect=blank):
        assert _post(client, auth_header, image)['code'] == 8006


def test_model_failure(client, auth_header, user, folder):
    image = _own_photo(folder, user.id)
    err = ApiError('抠图失败', code=8007)
    with patch.object(ai_services.CutoutService, '_remove_background', side_effect=err):
        assert _post(client, auth_header, image)['code'] == 8007


def test_reject_other_users_image(client, auth_header, user, other_user, folder):
    image = _own_photo(folder, other_user.id)
    with patch.object(ai_services.CutoutService, '_remove_background') as mocked:
        assert _post(client, auth_header, image)['code'] == 8002
    mocked.assert_not_called()


def test_reject_broken_file(client, auth_header, user, folder):
    (folder / f'{user.id}_broken.jpg').write_bytes(b'not an image')
    with patch.object(ai_services.CutoutService, '_remove_background') as mocked:
        assert _post(client, auth_header, f'/uploads/{user.id}_broken.jpg')['code'] == 8002
    mocked.assert_not_called()


def test_rate_limit(app, client, auth_header, user, folder):
    app.config['AI_CUTOUT_LIMIT_PER_HOUR'] = 3
    image = _own_photo(folder, user.id)
    with patch.object(ai_services.CutoutService, '_remove_background', side_effect=_fake_cutout):
        for _ in range(3):
            assert _post(client, auth_header, image)['code'] == 0
        assert _post(client, auth_header, image)['code'] == 8004


def test_daily_limit(app, client, auth_header, user, folder):
    app.config['AI_CUTOUT_LIMIT_PER_HOUR'] = 10
    app.config['AI_CUTOUT_LIMIT_PER_DAY'] = 2
    image = _own_photo(folder, user.id)
    with patch.object(ai_services.CutoutService, '_remove_background', side_effect=_fake_cutout):
        for _ in range(2):
            assert _post(client, auth_header, image)['code'] == 0
        body = _post(client, auth_header, image)
        assert body['code'] == 8004 and '今天' in body['msg']


# ---------------- 只保留主体 ----------------
def _cutout_with(rects, size=(400, 400)):
    """生成一张透明图，rects 里的每个矩形是一个不透明色块"""
    def fake(image):
        out = Image.new('RGBA', size, (0, 0, 0, 0))
        for (x, y, w, h) in rects:
            out.paste(Image.new('RGBA', (w, h), (255, 0, 0, 255)), (x, y))
        return out
    return fake


def _saved(folder, body):
    return Image.open(folder / body['data']['path'].rsplit('/', 1)[-1])


def test_clutter_removed(client, auth_header, user, folder):
    """衣服旁边的小杂物（不相连）会被去掉，只剩衣服"""
    image = _own_photo(folder, user.id, size=(400, 400))
    rects = [(150, 120, 120, 200),   # 衣服：120×200
             (10, 10, 40, 40),       # 杯子
             (330, 340, 50, 30)]     # 手机
    with patch.object(ai_services.CutoutService, '_remove_background', side_effect=_cutout_with(rects)):
        body = _post(client, auth_header, image)

    w, h = _saved(folder, body).size
    # 只剩衣服本身 + 少量边距，没有被杂物撑大
    assert 120 <= w <= 140 and 200 <= h <= 220


def test_pair_of_shoes_both_kept(client, auth_header, user, folder):
    """一双鞋两只大小相近，都要保留"""
    image = _own_photo(folder, user.id, size=(400, 400))
    rects = [(40, 150, 120, 80), (240, 170, 110, 80)]
    with patch.object(ai_services.CutoutService, '_remove_background', side_effect=_cutout_with(rects)):
        body = _post(client, auth_header, image)

    w, _ = _saved(folder, body).size
    assert w >= 310                  # 横跨两只鞋
