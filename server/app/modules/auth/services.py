# -*- coding: utf-8 -*-
"""
认证业务逻辑层
只处理业务规则，不处理 HTTP 请求/响应
"""
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Tuple

from flask import current_app
from flask_jwt_extended import create_access_token

from app.common.errors import ApiError
from app.extensions import db
from app.models.item import Item
from app.models.outfit import Outfit, OutfitItem
from app.models.user import User
from app.models.wear_log import WearLog

# 邮箱正则（RFC 5322 简化版）
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

# 微信 code 换 openid 接口
WX_CODE2SESSION_URL = 'https://api.weixin.qq.com/sns/jscode2session'
WX_REQUEST_TIMEOUT_SECONDS = 5
# 微信 code 无效 / 已使用 / 过期等，属于前端需要重新 wx.login 的情况
WX_INVALID_CODE_ERRCODES = {40029, 40163}
WX_DEFAULT_NICKNAME = '衣橱主人'


class AuthService:
    """注册 / 登录 / 用户信息"""

    # ---------------- 注册 ----------------
    @staticmethod
    def register(username: str, email: str, password: str) -> User:
        """
        用户注册
        :raises ApiError: 参数错误 / 用户名或邮箱已存在
        """
        # 1. 基础校验
        AuthService._validate_register_params(username, email, password)

        # 2. 唯一性校验（仅查未删除用户）
        if User.query.filter_by(username=username, deleted_at=None).first():
            raise ApiError('用户名已存在', code=1001)

        if User.query.filter_by(email=email, deleted_at=None).first():
            raise ApiError('邮箱已被注册', code=1002)

        # 3. 创建用户
        user = User(username=username, email=email, nickname=username)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()
        return user

    # ---------------- 登录 ----------------
    @staticmethod
    def login(account: str, password: str) -> Tuple[User, str]:
        """
        用户登录：支持用户名或邮箱
        :return: (用户对象, JWT access_token)
        :raises ApiError: 账号不存在或密码错误
        """
        if not account or not password:
            raise ApiError('账号和密码不能为空', code=1004)

        # 按用户名或邮箱查找（排除已删除用户）
        user = User.query.filter(
            db.or_(User.username == account, User.email == account),
            User.deleted_at.is_(None)
        ).first()

        if not user or not user.check_password(password):
            # 统一提示，不暴露具体是账号不存在还是密码错误
            raise ApiError('用户名或密码错误', code=1003)

        # 生成 JWT（identity 为 user.id）
        access_token = create_access_token(identity=str(user.id))
        return user, access_token

    # ---------------- 微信一键登录 ----------------
    @staticmethod
    def wx_login(code: str) -> Tuple[User, str, bool]:
        """
        小程序 wx.login 拿到的 code → openid → 查找或创建用户
        :return: (用户对象, JWT access_token, 是否新建用户)
        :raises ApiError: 1004 参数错误 / 1006 未配置 / 1007 code 无效 / 1008 微信服务不可用
        """
        code = (code or '').strip() if isinstance(code, str) else ''
        if not code:
            raise ApiError('缺少微信登录 code', code=1004)

        openid = AuthService._code_to_openid(code)

        # openid 唯一索引包含已软删除的账号：旧账号已删除时先释放 openid，再按新用户创建
        user = User.query.filter_by(openid=openid).first()
        if user and user.deleted_at is not None:
            user.openid = None
            db.session.flush()
            user = None

        is_new = user is None
        if is_new:
            user = User(username=AuthService._generate_wx_username(), openid=openid,
                        nickname=WX_DEFAULT_NICKNAME)
            db.session.add(user)
        db.session.commit()

        access_token = create_access_token(identity=str(user.id))
        return user, access_token, is_new

    @staticmethod
    def _code_to_openid(code: str) -> str:
        """调用微信 jscode2session。AppSecret 只放在请求里，绝不写进日志"""
        appid = (current_app.config.get('WX_APPID') or '').strip()
        secret = (current_app.config.get('WX_APPSECRET') or '').strip()
        if not appid or not secret:
            raise ApiError('微信登录未配置', code=1006)

        query = urllib.parse.urlencode({
            'appid': appid,
            'secret': secret,
            'js_code': code,
            'grant_type': 'authorization_code',
        })
        data = AuthService._fetch_wx_json(f'{WX_CODE2SESSION_URL}?{query}')

        errcode = data.get('errcode') or 0
        if errcode in WX_INVALID_CODE_ERRCODES:
            raise ApiError('微信登录凭证已失效，请重试', code=1007)
        if errcode:
            current_app.logger.warning('jscode2session 返回错误 errcode=%s', errcode)
            raise ApiError('微信登录失败，请稍后再试', code=1008)

        openid = data.get('openid')
        if not isinstance(openid, str) or not openid:
            raise ApiError('微信登录失败，请稍后再试', code=1008)
        return openid

    @staticmethod
    def _fetch_wx_json(url: str) -> dict:
        """GET 微信接口并解析 JSON；异常日志里不带 URL（URL 含 AppSecret）"""
        try:
            with urllib.request.urlopen(url, timeout=WX_REQUEST_TIMEOUT_SECONDS) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            current_app.logger.warning('jscode2session 请求失败：%s', type(e).__name__)
            raise ApiError('微信服务暂时不可用，请稍后再试', code=1008)
        try:
            data = json.loads(raw.decode('utf-8'))
        except ValueError:
            raise ApiError('微信服务返回格式异常', code=1008)
        if not isinstance(data, dict):
            raise ApiError('微信服务返回格式异常', code=1008)
        return data

    @staticmethod
    def _generate_wx_username() -> str:
        """微信账号的内部用户名：wx_ + 10 位随机串，撞名就重试"""
        for _ in range(5):
            candidate = f'wx_{secrets.token_hex(5)}'
            if not User.query.filter_by(username=candidate).first():
                return candidate
        raise ApiError('创建账号失败，请重试', code=1008)

    # ---------------- 注销账号 ----------------
    @staticmethod
    def delete_account(user_id: int) -> dict:
        """
        注销账号：彻底删除（不是软删除）该用户的全部数据，不可恢复
          1. 同一事务内删除：日记 → 搭配关联 → 搭配 → 衣物 → 用户
          2. 事务提交成功后，删除上传目录里该用户的全部图片（文件名以 <user_id>_ 开头）
        不依赖数据库外键级联，显式按 user_id 删除，保证只删自己的数据
        :return: { deleted_files: 删除的图片文件数 }
        :raises ApiError: 1005 用户不存在
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ApiError('用户不存在或已被删除', code=1005)

        try:
            outfit_ids = [row.id for row in Outfit.query.with_entities(Outfit.id).filter_by(user_id=user_id)]
            item_ids = [row.id for row in Item.query.with_entities(Item.id).filter_by(user_id=user_id)]

            WearLog.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            if outfit_ids or item_ids:
                OutfitItem.query.filter(
                    db.or_(OutfitItem.outfit_id.in_(outfit_ids or [-1]), OutfitItem.item_id.in_(item_ids or [-1]))
                ).delete(synchronize_session=False)
            Outfit.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            Item.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            db.session.delete(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('注销账号失败 user_id=%s', user_id)
            raise ApiError('注销失败，请稍后再试', code=1009)

        return {'deleted_files': AuthService._delete_user_files(user_id)}

    @staticmethod
    def _delete_user_files(user_id: int) -> int:
        """删除上传目录中以 <user_id>_ 开头的文件；单个文件删除失败只记日志，不影响注销结果"""
        folder = current_app.config.get('UPLOAD_FOLDER')
        if not folder or not os.path.isdir(folder):
            return 0
        prefix = f'{user_id}_'
        count = 0
        for name in os.listdir(folder):
            if not name.startswith(prefix):
                continue
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            try:
                os.remove(path)
                count += 1
            except OSError as e:
                current_app.logger.warning('注销时删除图片失败 %s：%s', name, type(e).__name__)
        return count

    # ---------------- 获取当前用户 ----------------
    @staticmethod
    def get_user_by_id(user_id: int) -> User:
        """
        按 ID 查询有效用户
        :raises ApiError: 用户不存在或已删除
        """
        user = User.query.filter_by(id=user_id, deleted_at=None).first()
        if not user:
            raise ApiError('用户不存在或已被删除', code=1005)
        return user

    # ---------------- 内部校验 ----------------
    @staticmethod
    def _validate_register_params(username: str, email: str, password: str) -> None:
        """注册参数校验"""
        if not username or not username.strip():
            raise ApiError('用户名不能为空', code=1004)

        username = username.strip()
        if len(username) < 2 or len(username) > 20:
            raise ApiError('用户名长度需为 2-20 个字符', code=1004)

        if not email or not email.strip():
            raise ApiError('邮箱不能为空', code=1004)

        email = email.strip()
        if not EMAIL_PATTERN.match(email):
            raise ApiError('邮箱格式不正确', code=1004)

        if not password:
            raise ApiError('密码不能为空', code=1004)

        if len(password) < 6:
            raise ApiError('密码长度至少为 6 位', code=1004)
