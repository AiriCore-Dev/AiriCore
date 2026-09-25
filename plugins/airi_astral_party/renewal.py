import copy
import getpass
import hashlib
import http.client
import json
import math
import platform
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from dataclasses import replace
from pathlib import Path

from filelock import FileLock, Timeout

from .protocol import QueryError
from .settings import CLIENT_VERSION, load_settings


AUTHORIZE_URL = 'https://m-sdk.feimogames.com/account/authorize'
REFRESH_SECONDS = 6 * 3600
APP_SIGN_KEYS = {
    '110001950': '67f6128727f2d8345a30d2d041797571',
    '110001958': '6586f8d6ab34f805997a06732fa181df',
}
AUTH_KEYS = {'provider', 'phone', 'password_digest', 'sdk_channel', 'device_name',
             'os_version', 'user_id', 'session_at'}


def _text(value, maximum=8192, empty=False):
    return isinstance(value, str) and (empty or bool(value.strip())) and len(value) <= maximum and not any(ord(c) < 32 for c in value)


def validate_authorization(auth):
    if not isinstance(auth, dict):
        raise QueryError('续期配置格式无效')
    if not auth:
        return
    if set(auth) != AUTH_KEYS or auth['provider'] != 'feimo':
        raise QueryError('续期配置不是受支持的飞魔账号配置，请管理员检查本地配置')
    if not isinstance(auth['phone'], str) or not re.fullmatch(r'1[0-9]{10}', auth['phone']):
        raise QueryError('飞魔账号手机号格式无效')
    if not isinstance(auth['password_digest'], str) or not re.fullmatch(r'[0-9a-f]{32}', auth['password_digest']):
        raise QueryError('飞魔账号凭据格式无效，请管理员检查本地配置')
    for key in ('sdk_channel', 'device_name', 'os_version', 'user_id'):
        if not _text(auth[key], 512, empty=key == 'user_id'):
            raise QueryError('续期配置中的设备或账号字段无效')
    value = auth['session_at']
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise QueryError('续期配置中的时间无效')
    if value and not auth['user_id']:
        raise QueryError('续期配置缺少飞魔账号标识，请管理员检查本地配置')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise QueryError('授权服务要求重定向，已停止发送凭据；请检查协议版本')


def request_json(method, url, data=None):
    if url != AUTHORIZE_URL or method != 'POST':
        raise QueryError('授权请求地址不在允许范围内')
    encoded = urllib.parse.urlencode(data or {}).encode('utf-8')
    request = urllib.request.Request(url, data=encoded, method=method, headers={
        'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded',
    })
    try:
        opener = urllib.request.build_opener(NoRedirect())
        try:
            response = opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            error.close()
            raise QueryError('飞魔授权服务拒绝请求或暂不可用，请检查账号状态或稍后重试') from None
        with response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise QueryError('授权服务响应超过限制')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except QueryError:
        raise
    except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException):
        raise QueryError('飞魔授权请求失败，请检查网络和系统时间；未输出服务端原文') from None


def password_digest(password):
    if not _text(password, 512):
        raise QueryError('密码为空或格式不受支持')
    first = hashlib.md5(password.encode('utf-8')).hexdigest()
    return hashlib.md5((password + first).encode('utf-8')).hexdigest()


def sdk_sign(values, app_id):
    signing_key = APP_SIGN_KEYS.get(app_id)
    if signing_key is None:
        raise QueryError('当前应用标识尚未适配飞魔签名，请核对客户端 SDK 配置')
    text = ''.join(key + '=' + values[key] for key in sorted(values)) + signing_key
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def _check_settings(settings):
    settings.validate(require_session=False)
    if settings.extra != 'bn' or settings.client_version != CLIENT_VERSION:
        raise QueryError('飞魔自动登录目前仅适配已解析的 3.2.1 飞魔 SDK，请核对客户端版本')
    sdk_sign({}, settings.app_id)


def _game_session(settings, auth, now):
    values = {
        'channel': auth['sdk_channel'], 'app_id': settings.app_id, 'sdk_version': '1.0.0.9',
        'device_id': settings.device_id, 'imei': '', 'time': str(round(now)), 'oaid': '', 'os': 'windows',
        'login_type': '19', 'os_version': auth['os_version'], 'device_name': auth['device_name'],
        'ad_id': '', 'and_id': settings.device_id, 'tel_num': auth['phone'], 'password': auth['password_digest'],
    }
    values['sign'] = sdk_sign(values, settings.app_id)
    result = request_json('POST', AUTHORIZE_URL, data=values)
    content = result.get('content')
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            content = None
    ret = result.get('ret')
    if not (type(ret) is int and ret == 1 or type(ret) is str and ret == '1') or not isinstance(content, dict):
        raise QueryError('飞魔账号登录未成功，请检查手机号、密码、应用渠道与版本；需要验证时请使用官方客户端')
    sid, user_id = content.get('authorize_code'), content.get('user_id')
    if type(user_id) is int:
        user_id = str(user_id)
    if not _text(sid) or not _text(user_id, 512):
        raise QueryError('飞魔未返回完整会话和账号标识，原配置已保留')
    if auth['user_id'] and auth['user_id'] != user_id:
        raise QueryError('飞魔返回了不同账号，已停止更新；请核对专用账号后私聊 astral 验证码 account login 手机号 密码')
    return sid, user_id


def refresh(path, now=None, force=False):
    from .account_setup import write_settings
    path = Path(path)
    if not path.is_file():
        raise QueryError('未找到账号配置，请管理员私聊 astral 验证码 account login 手机号 密码')
    try:
        with FileLock(str(path) + '.lock', timeout=3):
            settings = load_settings(path)
            _check_settings(settings)
            if not settings.renewal:
                raise QueryError('尚未配置自动登录，请管理员私聊 astral 验证码 account login 手机号 密码')
            now = time.time() if now is None else now
            auth = copy.deepcopy(settings.renewal)
            if not force and auth['session_at'] and 0 <= now - auth['session_at'] < REFRESH_SECONDS:
                return False
            sid, user_id = _game_session(settings, auth, now)
            auth.update(user_id=user_id, session_at=now)
            write_settings(path, replace(settings, sid=sid, extra='bn', renewal=auth))
            return True
    except Timeout:
        raise QueryError('其他进程正在更新授权，请稍后重试') from None


def login(path, sdk_channel='test_junhai'):
    path = Path(path)
    if not path.is_file():
        raise QueryError('尚无服务器配置；可在 Bot 私聊使用 astral 验证码 account login 手机号 密码 完成首次配置')
    if not _text(sdk_channel, 512):
        raise QueryError('SDK 安装渠道标识无效')
    try:
        with FileLock(str(path) + '.lock', timeout=3):
            settings = load_settings(path)
            _check_settings(settings)
            print('请输入已在官方客户端完成注册及验证的飞魔专用账号。手机号和密码均不回显。')
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', getpass.GetPassWarning)
                    phone = getpass.getpass('飞魔账号手机号：').strip()
                    digest = password_digest(getpass.getpass('飞魔账号密码：'))
            except getpass.GetPassWarning:
                raise QueryError('当前终端无法隐藏输入，请在交互式终端运行；不会使用明文输入回退') from None
            _save_login(path, settings, phone, digest, sdk_channel)
    except Timeout:
        raise QueryError('其他进程正在更新授权，请稍后重试') from None


def _save_login(path, settings, phone, digest, sdk_channel):
    from .account_setup import write_settings
    _check_settings(settings)
    auth = {'provider': 'feimo', 'phone': phone, 'password_digest': digest,
            'sdk_channel': sdk_channel, 'device_name': platform.node() or 'AiriCore',
            'os_version': platform.platform(), 'user_id': '', 'session_at': 0}
    validate_authorization(auth)
    now = time.time()
    sid, user_id = _game_session(settings, auth, now)
    auth.update(user_id=user_id, session_at=now)
    write_settings(path, replace(settings, sid=sid, extra='bn', renewal=auth))


def login_credentials(path, phone, digest):
    from .bootstrap import initial_settings
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with FileLock(str(path) + '.lock', timeout=3):
            settings = load_settings(path) if path.exists() else initial_settings()
            sdk_channel = settings.renewal.get('sdk_channel', 'test_junhai')
            _save_login(path, settings, phone, digest, sdk_channel)
    except Timeout:
        raise QueryError('其他进程正在更新授权，请稍后重试') from None


def clear_credentials(path):
    from .account_setup import write_settings
    path = Path(path)
    if not path.is_file():
        return
    try:
        with FileLock(str(path) + '.lock', timeout=3):
            settings = load_settings(path)
            write_settings(path, replace(settings, sid='', renewal={}))
    except Timeout:
        raise QueryError('其他进程正在更新授权，请稍后重试') from None


def authorization_status(settings):
    auth = settings.renewal
    if not auth:
        return '尚未配置飞魔自动登录，请管理员私聊 astral 验证码 account help'
    if not auth['session_at']:
        return '飞魔游戏会话待更新，请管理员私聊 astral 验证码 account refresh'
    age = time.time() - auth['session_at']
    if age < 0:
        return '续期时间异常，请检查系统时间'
    if age >= REFRESH_SECONDS:
        return '已到会话更新间隔；若持续未更新，请管理员检查账号'
    return '已配置飞魔自动登录，由 Bot 持续更新会话'
