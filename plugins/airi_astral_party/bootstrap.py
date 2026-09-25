import http.client
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import replace
from pathlib import Path

from filelock import FileLock, Timeout

from .protocol import QueryError
from .renewal import APP_SIGN_KEYS, NoRedirect
from .settings import CLIENT_VERSION, Settings, load_settings


DEFAULT_APP_ID = '110001958'
VERSION = '3.2.1'
SERVER_URL = 'https://se-web-cn.feimogames.com:7878/api/hotaddressServer/get'


def request_server(app_id):
    if app_id not in APP_SIGN_KEYS:
        raise QueryError('该飞魔应用尚未适配，请使用已支持的应用标识')
    url = SERVER_URL + '?' + urllib.parse.urlencode({'route': app_id, 'version': VERSION})
    try:
        with urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(url), timeout=15) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except urllib.error.HTTPError as error:
        error.close()
        raise QueryError('官方服务器引导暂不可用，请稍后重试') from None
    except QueryError:
        raise
    except (ValueError, OSError, http.client.HTTPException):
        raise QueryError('无法读取官方服务器配置，请检查网络或稍后重试') from None


def discover(app_id):
    result = request_server(app_id)
    if result.get('version') != VERSION or result.get('route') != app_id:
        raise QueryError('官方引导未提供当前应用与版本的服务器，请稍后重试或更新插件')
    address = result.get('serverUrl')
    if not isinstance(address, str) or not re.fullmatch(r'[a-zA-Z0-9.-]+:8800', address):
        raise QueryError('官方服务器地址缺失或格式不受支持，未保存配置')
    host, port = address.rsplit(':', 1)
    if not host.endswith('.feimogames.com') or not all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label) for label in host.split('.')):
        raise QueryError('官方服务器地址不在支持的域名范围内，未保存配置')
    return host, int(port)


def initial_settings(app_id=DEFAULT_APP_ID):
    host, port = discover(app_id)
    return Settings(host=host, port=port, game_id='120000182', channel_id='2', app_id=app_id,
                    extra='bn', device_id=secrets.token_hex(16), client_version=CLIENT_VERSION)


def setup(path, app_id=None):
    from .account_setup import write_settings
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with FileLock(str(path) + '.lock', timeout=3):
            current = load_settings(path) if path.exists() else None
            app_id = app_id or (current.app_id if current else DEFAULT_APP_ID)
            if current and (current.sid or current.renewal) and app_id != current.app_id:
                raise QueryError('更换应用前请先清除查询账号凭据，再重新登录')
            if current and app_id == current.app_id:
                host, port = discover(app_id)
                settings = replace(current, host=host, port=port)
            else:
                settings = initial_settings(app_id)
            write_settings(path, settings)
    except Timeout:
        raise QueryError('其他进程正在更新授权，请稍后重试') from None
