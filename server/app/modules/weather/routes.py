# -*- coding: utf-8 -*-
"""
天气路由层
GET /api/weather?lat=30.27&lon=120.15   需 JWT
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.common.response import success
from app.modules.weather.services import WeatherService

weather_bp = Blueprint('weather', __name__)


@weather_bp.get('')
@jwt_required()
def get_weather():
    """
    按经纬度查询实时天气
    返回: { temperature: 18.0, text: '晴', city: '杭州' }
    """
    data = WeatherService.get_now(request.args.get('lat'), request.args.get('lon'))
    return success(data=data)
