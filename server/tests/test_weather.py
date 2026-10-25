# -*- coding: utf-8 -*-
"""GET /api/weather：未配置、参数校验、正常返回、缓存。"""
from unittest.mock import patch

import pytest

from app.common.errors import ApiError
from app.modules.weather import services as weather_services

NOW_OK = {'code': '200', 'now': {'temp': '18', 'text': '晴'}}
CITY_OK = {'code': '200', 'location': [{'name': '杭州', 'adm2': '杭州'}]}


@pytest.fixture(autouse=True)
def _clear_cache():
    weather_services._cache.clear()
    yield
    weather_services._cache.clear()


@pytest.fixture
def configured(app):
    app.config['QWEATHER_API_KEY'] = 'test-key'
    app.config['QWEATHER_API_HOST'] = 'test.qweatherapi.com'


def _get(client, auth_header, **params):
    return client.get('/api/weather', query_string=params, headers=auth_header).get_json()


def test_not_configured(app, client, auth_header):
    app.config['QWEATHER_API_KEY'] = ''
    assert _get(client, auth_header, lat=30.27, lon=120.15)['code'] == 7001


def test_bad_coords(client, auth_header, configured):
    assert _get(client, auth_header, lat='abc', lon=120)['code'] == 7002
    assert _get(client, auth_header, lat=95, lon=120)['code'] == 7002


def test_success_and_cache(client, auth_header, configured):
    def fake_fetch(host, key, path, params):
        assert params['location'] == '120.15,30.27'      # 经度在前
        return NOW_OK if path == '/v7/weather/now' else CITY_OK

    with patch.object(weather_services.WeatherService, '_fetch_json', side_effect=fake_fetch) as mocked:
        body = _get(client, auth_header, lat=30.27, lon=120.15)
        assert body['code'] == 0
        assert body['data'] == {'temperature': 18.0, 'text': '晴', 'city': '杭州'}

        # 附近位置命中缓存，不再请求和风天气
        _get(client, auth_header, lat=30.271, lon=120.152)
        assert mocked.call_count == 2


def test_city_lookup_failure_is_not_fatal(client, auth_header, configured):
    def fake_fetch(host, key, path, params):
        if path == '/v7/weather/now':
            return NOW_OK
        raise ApiError('x', code=7003)

    with patch.object(weather_services.WeatherService, '_fetch_json', side_effect=fake_fetch):
        body = _get(client, auth_header, lat=30.27, lon=120.15)
        assert body['data']['temperature'] == 18.0
        assert body['data']['city'] == ''


def test_upstream_error(client, auth_header, configured):
    with patch.object(weather_services.WeatherService, '_fetch_json', return_value={'code': '401'}):
        assert _get(client, auth_header, lat=30.27, lon=120.15)['code'] == 7003
