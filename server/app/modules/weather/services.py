# -*- coding: utf-8 -*-
"""
天气业务逻辑层（和风天气 QWeather）

- 前端只上传经纬度，API Key 只保存在后端（环境变量），不会暴露给浏览器
- 同一位置（经纬度保留 2 位小数，约 1km）10 分钟内复用缓存，节省调用次数
- 只用 Python 标准库发请求，不新增依赖
"""
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from flask import current_app

from app.common.errors import ApiError

CACHE_TTL_SECONDS = 600
REQUEST_TIMEOUT_SECONDS = 5

# 进程内缓存：{(lat, lon): (过期时间戳, 结果)}
_cache: Dict[Tuple[float, float], Tuple[float, Dict[str, Any]]] = {}


class WeatherService:
    """按经纬度查询实时天气"""

    @staticmethod
    def get_now(lat: Any, lon: Any) -> Dict[str, Any]:
        """
        :return: { temperature, text, city }
        :raises ApiError: 7001 未配置 / 7002 参数错误 / 7003 天气服务不可用
        """
        latitude, longitude = WeatherService._parse_coords(lat, lon)

        key = (round(latitude, 2), round(longitude, 2))
        cached = _cache.get(key)
        if cached and cached[0] > time.time():
            return cached[1]

        api_key = (current_app.config.get('QWEATHER_API_KEY') or '').strip()
        api_host = (current_app.config.get('QWEATHER_API_HOST') or '').strip()
        if not api_key or not api_host:
            raise ApiError('天气服务未配置', code=7001)

        location = f'{longitude:.2f},{latitude:.2f}'   # 和风天气要求「经度,纬度」
        now = WeatherService._fetch_json(api_host, api_key, '/v7/weather/now', {'location': location})
        if not now or now.get('code') != '200' or not now.get('now'):
            current_app.logger.warning('QWeather now 返回异常：%s', now and now.get('code'))
            raise ApiError('天气获取失败，请稍后再试', code=7003)

        result = {
            'temperature': float(now['now'].get('temp')),
            'text': now['now'].get('text') or '',
            'city': WeatherService._lookup_city(api_host, api_key, location),
        }
        _cache[key] = (time.time() + CACHE_TTL_SECONDS, result)
        return result

    # ---------------- 内部 ----------------
    @staticmethod
    def _parse_coords(lat: Any, lon: Any) -> Tuple[float, float]:
        try:
            latitude = float(lat)
            longitude = float(lon)
        except (TypeError, ValueError):
            raise ApiError('经纬度格式不正确', code=7002)
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ApiError('经纬度超出范围', code=7002)
        return latitude, longitude

    @staticmethod
    def _lookup_city(api_host: str, api_key: str, location: str) -> str:
        """城市名查询失败不影响温度，返回空串即可"""
        try:
            data = WeatherService._fetch_json(api_host, api_key, '/geo/v2/city/lookup',
                                              {'location': location, 'number': 1})
            if data and data.get('code') == '200' and data.get('location'):
                place = data['location'][0]
                return place.get('name') or place.get('adm2') or ''
        except ApiError:
            pass
        return ''

    @staticmethod
    def _fetch_json(api_host: str, api_key: str, path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """GET 和风天气接口；响应可能是 gzip 压缩的，需要手动解压"""
        host = api_host if api_host.startswith('http') else f'https://{api_host}'
        url = f'{host.rstrip("/")}{path}?{urllib.parse.urlencode(params)}'
        req = urllib.request.Request(url, headers={
            'X-QW-Api-Key': api_key,
            'Accept-Encoding': 'gzip',
        })
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            current_app.logger.warning('QWeather 请求失败 %s：%s', path, e)
            raise ApiError('天气服务暂时不可用', code=7003)

        if raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        try:
            return json.loads(raw.decode('utf-8'))
        except ValueError:
            raise ApiError('天气服务返回格式异常', code=7003)
