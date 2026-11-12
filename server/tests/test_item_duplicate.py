# -*- coding: utf-8 -*-
"""重复照片检测：图片指纹计算、新增 / 详情 / 列表的「可能重复」、补算命令。"""
from datetime import datetime

import pytest
from PIL import Image, ImageDraw

from app.common import image_fingerprint as fpmod
from app.extensions import db
from app.models.item import Item
from tests.conftest import make_item


@pytest.fixture
def folder(app, tmp_path):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    return tmp_path


def _draw(path, shape='shirt', color=(30, 30, 30), size=(400, 500), transparent=False):
    """画一件「衣服」：白底（或透明底）上的纯色图形"""
    bg = (0, 0, 0, 0) if transparent else (255, 255, 255, 255)
    im = Image.new('RGBA', size, bg)
    d = ImageDraw.Draw(im)
    w, h = size
    fill = color + (255,)
    if shape == 'shirt':
        d.polygon([(w * .3, h * .1), (w * .7, h * .1), (w * .95, h * .3), (w * .8, h * .4),
                   (w * .75, h * .9), (w * .25, h * .9), (w * .2, h * .4), (w * .05, h * .3)], fill=fill)
    elif shape == 'pants':
        d.polygon([(w * .25, h * .05), (w * .75, h * .05), (w * .8, h * .95), (w * .55, h * .95),
                   (w * .5, h * .4), (w * .45, h * .95), (w * .2, h * .95)], fill=fill)
    else:  # bag
        d.ellipse([w * .15, h * .35, w * .85, h * .9], fill=fill)
        d.arc([w * .3, h * .1, w * .7, h * .55], 180, 360, fill=fill, width=12)
    if transparent:
        im.save(path, 'PNG')
    else:
        im.convert('RGB').save(path, 'JPEG', quality=85)
    return path


def _variant(src, dst):
    """模拟同一张照片再传一次：缩小一半 + 低质量 JPEG"""
    with Image.open(src) as im:
        im.convert('RGB').resize((im.width // 2, im.height // 2)).save(dst, 'JPEG', quality=60)
    return dst


def _create(client, header, name, **body):
    payload = {'image_url': f'/uploads/{name}', 'type': '上装', 'needs_review': True}
    payload.update(body)
    return client.post('/api/items', json=payload, headers=header).get_json()


# ---------------- 指纹本身 ----------------
def test_fingerprint_similar_and_different(folder):
    a = fpmod.compute(str(_draw(folder / 'a.jpg')))
    a2 = fpmod.compute(str(_variant(folder / 'a.jpg', folder / 'a2.jpg')))
    other_shape = fpmod.compute(str(_draw(folder / 'b.jpg', shape='bag')))
    other_color = fpmod.compute(str(_draw(folder / 'c.jpg', color=(230, 120, 160))))

    assert a and len(a) == 16 + 1 + 96
    assert fpmod.is_similar(a, a2, 10, 16)
    assert not fpmod.is_similar(a, other_shape, 10, 16)
    assert not fpmod.is_similar(a, other_color, 10, 16)   # 轮廓相同、颜色不同 → 不算重复


def test_transparent_cutout_matches_white_background(folder):
    """抠图后的透明 PNG 铺白底后，应与白底原图视为同一件"""
    white = fpmod.compute(str(_draw(folder / 'w.jpg')))
    cut = fpmod.compute(str(_draw(folder / 't.png', transparent=True)))
    assert fpmod.is_similar(white, cut, 10, 16)


def test_fingerprint_bad_input(folder):
    (folder / 'broken.jpg').write_bytes(b'not an image')
    assert fpmod.compute(str(folder / 'broken.jpg')) is None
    assert fpmod.compute(str(folder / 'missing.jpg')) is None
    assert fpmod.distance('zz:zz', '00:00') is None
    assert not fpmod.is_similar(None, 'x', 10, 16)


# ---------------- 新增 / 详情 ----------------
def test_create_reports_duplicates(client, auth_header, folder):
    _draw(folder / '1_a.jpg')
    first = _create(client, auth_header, '1_a.jpg')['data']
    assert first['duplicates'] == []

    _variant(folder / '1_a.jpg', folder / '1_a_again.jpg')
    second = _create(client, auth_header, '1_a_again.jpg')['data']
    assert [d['item_id'] for d in second['duplicates']] == [first['item_id']]
    assert second['duplicates'][0]['image_url'].endswith('/uploads/1_a.jpg')

    _draw(folder / '1_pants.jpg', shape='pants', color=(40, 70, 160))
    assert _create(client, auth_header, '1_pants.jpg', type='下装')['data']['duplicates'] == []

    detail = client.get(f"/api/items/{first['item_id']}", headers=auth_header).get_json()['data']
    assert [d['item_id'] for d in detail['duplicates']] == [second['item_id']]
    assert 'image_fp' not in detail          # 指纹不暴露给前端


def test_duplicates_ignore_other_users_and_deleted(client, auth_header, user, other_user, folder):
    _draw(folder / 'x.jpg')
    fp = fpmod.compute(str(folder / 'x.jpg'))
    make_item(other_user.id, image_url='/uploads/x.jpg', image_fp=fp)
    make_item(user.id, image_url='/uploads/x.jpg', image_fp=fp, deleted_at=datetime.utcnow())

    _variant(folder / 'x.jpg', folder / 'x2.jpg')
    assert _create(client, auth_header, 'x2.jpg')['data']['duplicates'] == []


def test_external_image_has_no_fingerprint(client, auth_header, folder):
    body = _create(client, auth_header, 'unused', image_url='https://example.com/a.jpg')
    assert body['code'] == 0 and body['data']['duplicates'] == []
    assert db.session.get(Item, body['data']['item_id']).image_fp is None


def test_update_image_recomputes_fingerprint(client, auth_header, folder):
    _draw(folder / 'p.jpg', shape='pants')
    _draw(folder / 'q.jpg', shape='bag', color=(200, 40, 40))
    item_id = _create(client, auth_header, 'p.jpg')['data']['item_id']
    before = db.session.get(Item, item_id).image_fp

    client.put(f'/api/items/{item_id}', json={'image_url': '/uploads/q.jpg'}, headers=auth_header)
    after = db.session.get(Item, item_id).image_fp
    assert after and after != before


# ---------------- 列表 ----------------
def test_list_marks_pending_duplicates(client, auth_header, folder):
    _draw(folder / 'old.jpg')
    old = _create(client, auth_header, 'old.jpg', needs_review=False)['data']
    _variant(folder / 'old.jpg', folder / 'new.jpg')
    new = _create(client, auth_header, 'new.jpg')['data']
    _draw(folder / 'bag.jpg', shape='bag', color=(200, 40, 40))
    bag = _create(client, auth_header, 'bag.jpg', type='包包')['data']

    rows = {r['item_id']: r for r in client.get('/api/items', headers=auth_header).get_json()['data']['list']}
    assert rows[new['item_id']]['duplicate_of'] == old['item_id']
    assert rows[bag['item_id']]['duplicate_of'] is None
    assert rows[old['item_id']]['duplicate_of'] is None      # 已确认的不提示


# ---------------- 补算命令 ----------------
def test_backfill_command(app, user, folder):
    _draw(folder / 'b1.jpg')
    local = make_item(user.id, image_url='/uploads/b1.jpg')
    external = make_item(user.id, image_url='https://example.com/x.jpg')

    out = app.test_cli_runner().invoke(args=['backfill-image-fp']).output
    assert '处理 2 件衣物' in out and '成功计算 1 件' in out
    assert db.session.get(Item, local.id).image_fp
    assert db.session.get(Item, external.id).image_fp is None
