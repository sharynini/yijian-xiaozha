# -*- coding: utf-8 -*-
"""POST /api/upload：真实图片校验、按实际格式定扩展名、去除 EXIF、按方向转正、缩图、GIF 原样保存。"""
import io

import pytest
from PIL import Image


@pytest.fixture
def folder(app, tmp_path):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    return tmp_path


def _post(client, header, data, name):
    resp = client.post('/api/upload', data={'file': (io.BytesIO(data), name)}, headers=header,
                       content_type='multipart/form-data')
    return resp.get_json()


def _image_bytes(fmt, size=(40, 20), mode='RGB', exif=None):
    buf = io.BytesIO()
    kwargs = {'exif': exif} if exif is not None else {}
    Image.new(mode, size, 'red').save(buf, fmt, **kwargs)
    return buf.getvalue()


def _saved(folder, body):
    return folder / body['data']['path'].rsplit('/', 1)[-1]


def test_rejects_fake_image(client, auth_header, folder):
    body = _post(client, auth_header, b'not-an-image', 'a.jpg')
    assert body['code'] == 6001
    assert list(folder.iterdir()) == []


def test_rejects_bad_extension(client, auth_header, folder):
    assert _post(client, auth_header, _image_bytes('PNG'), 'a.exe')['code'] == 6001


def test_extension_follows_real_format(client, auth_header, folder, user):
    body = _post(client, auth_header, _image_bytes('PNG'), 'photo.jpg')
    assert body['code'] == 0
    assert body['data']['path'].startswith(f'/uploads/{user.id}_')
    assert body['data']['path'].endswith('.png')


def test_strips_exif_and_applies_orientation(client, auth_header, folder):
    exif = Image.Exif()
    exif[0x0112] = 6                       # Orientation：需要顺时针旋转 90°
    exif[0x8825] = {2: (30.0, 15.0, 0.0)}  # GPSInfo：模拟拍摄地点
    body = _post(client, auth_header, _image_bytes('JPEG', size=(40, 20), exif=exif), 'gps.jpg')
    assert body['code'] == 0
    with Image.open(_saved(folder, body)) as im:
        assert len(im.getexif()) == 0       # 元数据被清掉
        assert im.size == (20, 40)          # 已按方向转正


def test_downscales_large_image(app, client, auth_header, folder):
    app.config['UPLOAD_MAX_SIDE'] = 100
    body = _post(client, auth_header, _image_bytes('JPEG', size=(400, 200)), 'big.jpg')
    with Image.open(_saved(folder, body)) as im:
        assert im.size == (100, 50)


def test_png_keeps_transparency(client, auth_header, folder):
    body = _post(client, auth_header, _image_bytes('PNG', mode='RGBA'), 'cut.png')
    with Image.open(_saved(folder, body)) as im:
        assert im.mode == 'RGBA'


def test_gif_saved_as_is(client, auth_header, folder):
    raw = _image_bytes('GIF', mode='P')
    body = _post(client, auth_header, raw, 'a.gif')
    assert body['code'] == 0
    assert _saved(folder, body).read_bytes() == raw


def test_requires_login(client, folder):
    resp = client.post('/api/upload', data={'file': (io.BytesIO(_image_bytes('PNG')), 'a.png')},
                       content_type='multipart/form-data')
    assert resp.status_code == 401
