from dataclasses import dataclass, field
from pathlib import Path

from . import bootstrap, renewal
from .protocol import QueryError
from .settings import load_settings


@dataclass(frozen=True)
class Credentials:
    phone: str = field(repr=False)
    digest: str = field(repr=False)


HELP = [
    '仅超级用户私聊可用，每次操作都需要当前双重验证码。',
    '格式：astral 验证码 account 子指令',
    'help  ·  查看本帮助',
    'login 手机号 密码  ·  飞魔登录或更换专用账号',
    'setup [应用ID]  ·  获取官方服务器配置，可选应用标识',
    'refresh  ·  立即重新登录并更新游戏会话',
    'check  ·  离线检查配置，不展示任何凭据',
    'clear confirm  ·  清除本地查询凭据并停止自动登录',
    '首次 login 自动配置，无需运行游戏或命令行工具。',
    '登录后由 Bot 自动维护会话；密码支持中间空格。',
    '输入会尝试撤回，QQ 和 OneBot 上游仍可能保留记录。',
]


class AccountAdmin:
    def __init__(self, path, lock, run_sync):
        self.path = Path(path)
        self.lock = lock
        self.run_sync = run_sync

    async def handle(self, text, private, verified, credentials=None):
        if not private:
            raise QueryError('账号管理仅支持超级用户私聊，请勿在群聊发送凭据')
        if not verified:
            raise QueryError('需要超级用户权限及当前双重验证码：astral 验证码 account help')
        parts = text.split()
        if not parts or parts == ['help']:
            return self.notice('飞魔账号管理', HELP)
        async with self.lock:
            if parts == ['login'] and isinstance(credentials, Credentials):
                await self.run_sync(renewal.login_credentials, self.path, credentials.phone, credentials.digest)
                return self.notice('飞魔登录完成', ['查询账号已保存，Bot 将自动更新会话', '可发送 astral UID 验证实际玩家查询'])
            if parts[0] == 'setup' and len(parts) in (1, 2):
                await self.run_sync(bootstrap.setup, self.path, parts[1] if len(parts) == 2 else None)
                return self.notice('服务器配置完成', ['已从官方引导获取查询服务器', '下一步：astral 验证码 account login 手机号 密码'])
            if parts == ['refresh']:
                await self.run_sync(renewal.refresh, self.path, None, True)
                return self.notice('会话已更新', ['已使用飞魔凭据重新登录，后续查询使用新会话'])
            if parts == ['check']:
                settings = await self.run_sync(load_settings, self.path)
                return self.notice('飞魔账号状态', ['服务器已配置' if settings.host else '服务器尚未配置',
                                                  '游戏会话已保存' if settings.sid else '尚未登录',
                                                  renewal.authorization_status(settings),
                                                  '本地检查不代表服务端授权有效'])
            if parts == ['clear', 'confirm']:
                await self.run_sync(renewal.clear_credentials, self.path)
                return self.notice('凭据已清除', ['已清除本地会话和飞魔自动登录凭据', 'Bot 不再自动登录；玩家 UID 绑定仍保留'])
        raise QueryError('账号指令格式不正确，请发送 astral 验证码 account help；清除使用 clear confirm')

    async def maintain(self):
        async with self.lock:
            settings = await self.run_sync(load_settings, self.path)
            if not settings.renewal:
                return False
            return await self.run_sync(renewal.refresh, self.path)

    @staticmethod
    def notice(title, lines):
        return {'kind': 'notice', 'title': title, 'lines': lines}
