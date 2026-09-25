import asyncio
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout

from .client import GameClient
from .protocol import QueryError
from .settings import DATA_DIR, load_settings
from .renewal import authorization_status
from .replay import enrich_snapshot
from .watch import WatchClient
from .watch_store import GroupWatchStore, watch_code
from .whitelist import group_id


PAGE_SIZE = 6


@dataclass(frozen=True)
class Command:
    action: str
    uid: int | None = None
    number: int = 1
    watch_code: str | None = None


def player_id(value):
    if not re.fullmatch(r'[0-9]{1,19}', str(value)) or not 0 < int(value) < 2**63:
        raise QueryError('玩家 UID 应为有效的正整数，请从游戏个人资料页复制')
    return int(value)


def parse_command(text):
    if len(text) > 160:
        raise QueryError('指令过长，请发送“astral help”查看用法')
    parts = text.split()
    if not parts or parts.pop(0) != 'astral':
        raise QueryError('指令应以 astral 开头，请发送“astral help”查看用法')
    if not parts:
        return Command('帮助')
    action, *args = parts
    actions = {'help': '帮助', 'unbind': '解绑', 'status': '状态', 'card': '手牌', 'unwatch': '停止观战'}
    if action in actions and not args:
        return Command(actions[action])
    if action == 'bind' and len(args) == 1:
        return Command('绑定', player_id(args[0]))
    if action == 'watch' and len(args) == 1:
        return Command('观战', watch_code=watch_code(args[0]))
    if action == 'me' or re.fullmatch(r'[0-9]+', action):
        uid = None if action == 'me' else player_id(action)
        if not args:
            return Command('资料', uid)
        if args[0] == 'recent' and len(args) in (1, 2):
            return Command('战绩', uid, _number(args[1], 20, '页码') if len(args) == 2 else 1)
        if args[0] == 'battle' and len(args) == 2:
            return Command('对局', uid, _number(args[1], 100, '对局序号'))
    raise QueryError('指令格式不正确，请发送“astral help”查看用法')


def _number(value, maximum, label):
    if not re.fullmatch(r'[0-9]{1,3}', value) or not 1 <= int(value) <= maximum:
        raise QueryError(f'{label}应为 1 至 {maximum}')
    return int(value)


class BindingStore:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _read(self):
        if not self.path.exists():
            return {}
        try:
            if self.path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError
            for key, value in data.items():
                if not isinstance(key, str) or not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError
                player_id(value)
            return data
        except (OSError, ValueError, TypeError):
            raise QueryError('吉星派对绑定记录损坏或不可读，请联系管理员；原文件已保留') from None

    def get(self, user):
        with self._lock:
            return self._read().get(str(user))

    def set(self, user, uid):
        if uid is not None:
            uid = player_id(uid)
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, FileLock(str(self.path) + '.lock', timeout=3):
                data = self._read()
                if uid is None:
                    data.pop(str(user), None)
                else:
                    data[str(user)] = uid
                encoded = json.dumps(data, ensure_ascii=False, sort_keys=True).encode('utf-8')
                if len(encoded) > 2 * 1024 * 1024:
                    raise QueryError('绑定记录已达容量上限，请联系管理员')
                with tempfile.NamedTemporaryFile(dir=self.path.parent, suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
        except (OSError, Timeout):
            raise QueryError('绑定记录保存失败，原有绑定未变更，请稍后重试') from None
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink(missing_ok=True)


class QueryService:
    def __init__(self, directory=DATA_DIR, run_sync=asyncio.to_thread):
        self.directory = Path(directory)
        self.store = BindingStore(self.directory / 'bindings.json')
        self.watch_store = GroupWatchStore(self.directory / 'group_watch.json')
        self.run_sync = run_sync
        self._lock = asyncio.Lock()
        self._next_query = 0.0

    async def handle(self, text, user, group=None):
        command = parse_command(text)
        if command.action in {'观战', '手牌', '停止观战'}:
            return await self.handle_watch(command, group)
        if command.action == '帮助':
            return {'kind': 'help'}
        if command.action == '绑定':
            await self.run_sync(self.store.set, user, command.uid)
            return _notice('绑定成功', [f'查询默认 UID：{command.uid}', '绑定仅用于快捷查询，不代表账号认证', '发送“astral me”查看玩家资料'])
        if command.action == '解绑':
            await self.run_sync(self.store.set, user, None)
            return _notice('解绑完成', ['已移除你的默认查询 UID'])
        uid = command.uid or await self.run_sync(self.store.get, user)
        if command.action == '状态':
            settings = await self.run_sync(load_settings, self.directory / 'config.json')
            return _notice('查询状态', ['查询账号已配置' if settings.sid else '尚未配置专用查询账号',
                                       authorization_status(settings),
                                       f'默认 UID：{uid}' if uid else '尚未绑定默认 UID',
                                       '绑定不会登录或修改该玩家账号'])
        if uid is None:
            raise QueryError('使用 me 前请先发送“astral bind UID”绑定玩家；也可用“astral UID”直接查询')
        if self._lock.locked() or time.monotonic() < self._next_query:
            raise QueryError('吉星派对查询较频繁，请稍后重试')
        async with self._lock:
            settings = await self.run_sync(load_settings, self.directory / 'config.json')
            client = GameClient(settings)
            self._next_query = time.monotonic() + settings.cooldown
            snapshot = await client.fetch(uid, detail=command.number if command.action == '对局' else None)
            if command.action == '对局':
                snapshot = await self.run_sync(enrich_snapshot, snapshot)
            if command.action == '战绩' and (command.number - 1) * PAGE_SIZE >= max(1, len(snapshot['show']['record'])):
                raise QueryError('该战绩页不存在，请从第 1 页开始查看')
            return {'kind': {'资料': 'profile', '战绩': 'records', '对局': 'detail'}[command.action],
                    'snapshot': snapshot, 'page': command.number}

    async def handle_watch(self, command, group):
        if group is None:
            raise QueryError('watch、card 和 unwatch 仅支持群聊，请在需要观战的群内使用')
        group = group_id(group)
        if command.action == '停止观战':
            async with self._lock:
                removed = await self.run_sync(self.watch_store.delete, group)
            return _notice('本群观战已停止' if removed else '本群尚未观战',
                           ['已清除当前群的观战对局，其他群不受影响' if removed else '当前群没有已设置的观战对局'])
        if self._lock.locked() or time.monotonic() < self._next_query:
            raise QueryError('吉星派对查询较频繁，请稍后重试')
        async with self._lock:
            target = await self.run_sync(self.watch_store.get, group)
            if command.action == '手牌' and target is None:
                raise QueryError('本群尚未设置观战对局，请先发送 astral watch 观战码')
            settings = await self.run_sync(load_settings, self.directory / 'config.json')
            self._next_query = time.monotonic() + settings.cooldown
            code = command.watch_code if command.action == '观战' else target['code']
            expected = None if command.action == '观战' else target['room_id']
            result = await WatchClient(settings).fetch(code, expected_room=expected)
            if command.action == '观战':
                await self.run_sync(self.watch_store.set, group, code, result['room_id'])
                return _notice('本群观战已设置', ['当前群的观战对局已更新，其他群不受影响',
                    f'对局回合：{result["round"]}', '发送 astral card 查询当前可见手牌',
                    '每次查询获取一次快照，隐藏牌面显示为不可见'])
            return {'kind': 'hands', 'snapshot': {**result, 'watch_code': code}}


def _notice(title, lines):
    return {'kind': 'notice', 'title': title, 'lines': lines}
