import json
from dataclasses import dataclass, field, fields
from pathlib import Path

from .protocol import QueryError


DATA_DIR = Path('data/astral_party')
CLIENT_VERSION = '3.2.0'


@dataclass(frozen=True)
class Settings:
    host: str = ''
    port: int = 8800
    client_version: str = CLIENT_VERSION
    game_id: str = ''
    channel_id: str = ''
    app_id: str = ''
    sid: str = field(default='', repr=False)
    extra: str = field(default='', repr=False)
    device_id: str = field(default='', repr=False)
    timeout: float = 15.0
    cooldown: float = 10.0
    renewal: dict = field(default_factory=dict, repr=False)

    def validate(self, require_session=True):
        if not all(isinstance(getattr(self, key), str) and getattr(self, key).strip()
                   for key in ('host', 'game_id', 'channel_id', 'app_id', 'device_id')) or (
                       require_session and (not isinstance(self.sid, str) or not self.sid.strip())):
            raise QueryError('尚未配置吉星派对查询账号，请联系管理员配置专用账号')
        if not isinstance(self.port, int) or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise QueryError('吉星派对配置中的端口无效')
        if not isinstance(self.timeout, (int, float)) or not 0 < self.timeout <= 30:
            raise QueryError('吉星派对配置中的超时时间无效')
        if not isinstance(self.cooldown, (int, float)) or not 0 <= self.cooldown <= 300:
            raise QueryError('吉星派对配置中的查询间隔无效')
        if any(not isinstance(getattr(self, key), str) or len(getattr(self, key)) > 8192
               for key in ('client_version', 'extra', 'sid', 'host', 'game_id', 'channel_id', 'app_id', 'device_id')):
            raise QueryError('吉星派对配置字段格式无效')
        if not self.client_version.strip() or len(self.host) > 253 or any(c in self.host for c in '/\\@\r\n '):
            raise QueryError('吉星派对配置中的服务器地址或版本无效')
        from .renewal import validate_authorization
        validate_authorization(self.renewal)


def load_settings(path=None):
    path = Path(path) if path is not None else DATA_DIR / 'config.json'
    if not path.exists():
        return Settings()
    try:
        if path.stat().st_size > 65536:
            raise ValueError
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or set(data) - {f.name for f in fields(Settings)}:
            raise ValueError
        if data.get('client_version') == '3.2.1':
            data['client_version'] = CLIENT_VERSION
        settings = Settings(**data)
        settings.validate(require_session=False)
        return settings
    except (OSError, ValueError, TypeError):
        raise QueryError('吉星派对账号配置无效，请管理员检查本机配置文件') from None
