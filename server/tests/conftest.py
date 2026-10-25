# -*- coding: utf-8 -*-
"""穿搭日记接口测试夹具：内存 SQLite + JWT。"""
import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles

from app import create_app
from app.extensions import db
from app.models.item import Item
from app.models.user import User


@compiles(BigInteger, 'sqlite')
def _sqlite_bigint(_type, compiler, **_kw):
    """SQLite 仅 INTEGER PRIMARY KEY 会自增；生产库仍用 MySQL BIGINT。"""
    return 'INTEGER'


def _make_index_names_unique_for_sqlite():
    """
    MySQL 的索引名只需在单表内唯一（item / outfit / wear_log 都有 idx_user_id），
    SQLite 却要求整个库唯一。测试建表前给索引名加上表名前缀，不影响 MySQL 与迁移。
    """
    for table in db.metadata.tables.values():
        for index in table.indexes:
            if index.name and not index.name.startswith(f'{table.name}__'):
                index.name = f'{table.name}__{index.name}'


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        _make_index_names_unique_for_sqlite()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    account = User(username='alice', email='alice@example.com', nickname='alice')
    account.set_password('secret1')
    db.session.add(account)
    db.session.commit()
    return account


@pytest.fixture
def other_user(app):
    account = User(username='bob', email='bob@example.com', nickname='bob')
    account.set_password('secret1')
    db.session.add(account)
    db.session.commit()
    return account


@pytest.fixture
def auth_header(app, user):
    token = create_access_token(identity=str(user.id))
    return {'Authorization': f'Bearer {token}'}


def make_item(user_id, **kwargs):
    payload = {
        'user_id': user_id,
        'image_url': 'https://example.com/a.jpg',
        'type': '上装',
        'color': '白',
        'season': '春',
        'status': '正常',
        'wear_count': 0,
    }
    payload.update(kwargs)
    item = Item(**payload)
    db.session.add(item)
    db.session.commit()
    return item
