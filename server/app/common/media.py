# -*- coding: utf-8 -*-
"""
图片地址工具

约定：数据库里只存本站上传图片的「相对路径」（形如 /uploads/1_ab12.jpg），
接口返回给前端时再拼成完整地址。这样换域名、上 HTTPS、改成对象存储时，
库里的数据都不用动。

- to_storage_path(url)  写库前调用：本站图片完整地址 → /uploads/xxx；外部链接原样保留
- to_public_url(path)   返回前调用：/uploads/xxx → 完整地址；其它值原样返回

「本站图片」的判断（满足其一即可，且路径必须以 /uploads/ 开头）：
1. 主机名等于当前请求的主机，或等于 PUBLIC_BASE_URL 的主机；
2. 主机是 localhost / 回环地址 / 局域网 IP（历史开发数据都是这类地址）；
3. 主机在调用方传入的 extra_hosts 里（迁移脚本用）。
"""
import ipaddress
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

from flask import current_app, has_app_context, has_request_context, request

UPLOAD_PREFIX = '/uploads/'


def _hostname_of(netloc: str) -> str:
    """去掉端口与账号部分，只保留小写主机名"""
    return (urlparse(f'//{netloc}').hostname or '').lower()


def _is_local_host(hostname: str) -> bool:
    if hostname == 'localhost':
        return True
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def _own_hostnames(extra_hosts: Optional[Iterable[str]] = None) -> set:
    hosts = {_hostname_of(h) for h in (extra_hosts or []) if h}
    if has_request_context():
        hosts.add(_hostname_of(request.host))
    if has_app_context():
        base = (current_app.config.get('PUBLIC_BASE_URL') or '').strip()
        if base:
            hosts.add((urlparse(base).hostname or '').lower())
    hosts.discard('')
    return hosts


def to_storage_path(url: Any, extra_hosts: Optional[Iterable[str]] = None) -> Any:
    """
    写库前：把本站上传图片的完整地址转成 /uploads/xxx。
    None / 空串 / 外部链接 / 已是相对路径，均原样返回。
    """
    if not isinstance(url, str):
        return url
    value = url.strip()
    if not value or value.startswith(UPLOAD_PREFIX):
        return value

    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.path.startswith(UPLOAD_PREFIX):
        return value

    hostname = (parsed.hostname or '').lower()
    if _is_local_host(hostname) or hostname in _own_hostnames(extra_hosts):
        return parsed.path
    return value


def to_public_url(value: Any) -> Any:
    """
    返回前：把 /uploads/xxx 拼成完整地址。
    优先用配置 PUBLIC_BASE_URL；未配置时用当前请求的域名。
    历史遗留的本站完整地址也会先归一化再拼接，保证换域名后仍能访问。
    """
    if not isinstance(value, str) or not value:
        return value

    path = to_storage_path(value)
    if not isinstance(path, str) or not path.startswith(UPLOAD_PREFIX):
        return value

    base = ''
    if has_app_context():
        base = (current_app.config.get('PUBLIC_BASE_URL') or '').strip().rstrip('/')
    if not base and has_request_context():
        base = request.host_url.rstrip('/')
    return f'{base}{path}' if base else path
