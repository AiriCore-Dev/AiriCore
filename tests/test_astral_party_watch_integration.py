import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GroupWatchIntegrationTests(unittest.TestCase):
    def test_group_routes_billing_privacy_and_refunds(self):
        program = r'''
import asyncio
import base64
import importlib
import io
from unittest.mock import AsyncMock, patch

import nonebot
from nonebot.adapters.onebot.v11 import Adapter, Message
from PIL import Image

nonebot.init(_env_file=None, driver='~fastapi', command_start={'', '/'})
nonebot.get_driver().register_adapter(Adapter)
plugin = nonebot.load_plugin('plugins.airi_astral_party')
assert plugin is not None
app = plugin.module
from plugins.airi_astral_party import runtime, watch
service = importlib.import_module('plugins.airi_astral_party.service')
from plugins.airi_astral_party.protocol import QueryError
from plugins.airi_astral_party.settings import Settings
from utils import credit
from utils.messaging import SendResult

def event(args, user, group):
    raw = 'astral ' + args
    data = dict(time=1, self_id=2, post_type='message', message_id=3, user_id=user,
                message=[{'type': 'text', 'data': {'text': raw}}], raw_message=raw, font=0,
                sender={'user_id': user, 'nickname': '测试'},
                message_type='group' if group else 'private', sub_type='normal' if group else 'friend')
    if group:
        data['group_id'] = group
    return Adapter.json_to_event(data)

async def main():
    bot = AsyncMock()
    calls = []
    async def fetch(code, expected_room=None):
        calls.append((code, expected_room))
        if code == 'BAD':
            raise QueryError('观战码无效')
        room = '100' if code == 'A' else '200'
        assert expected_room is None or expected_room == room
        return {'room_id': room, 'map_type': 4, 'round': 8, 'captured_at': 1700000000,
            'players': [{'uid': str(i + 1), 'slot': i, 'name': f'测试玩家{i}', 'hero_id': 101,
                         'cards': [{'id': None}, {'id': 21001}, {'id': 999999}]} for i in range(4)]}
    async def invoke(args, user=1, group=4):
        await app.handle(bot, event(args, user, group), ('astral',), Message(args))
    app.group_whitelist.add(4)
    app.group_whitelist.add(5)
    await credit.credit('1', 100)
    await credit.credit('2', 30)
    with patch.object(service, 'load_settings', return_value=Settings(cooldown=0)), \
         patch.object(watch.WatchClient, 'fetch', side_effect=fetch), \
         patch.object(app, 'send_group_with_fallback', new_callable=AsyncMock,
                      return_value=SendResult(True, '2', None)) as send_group, \
         patch.object(app.credit, 'charge', wraps=app.credit.charge) as charge:
        for args in ('watch A', 'card', 'unwatch'):
            await invoke(args, group=6)
            await invoke(args, group=None)
        assert not calls and charge.call_count == 0
        assert send_group.call_count == 0
        assert app.service.watch_store.get(6) is None
        await invoke('watch A')
        assert await credit.get_balance('1') == 100
        assert app.service.watch_store.get(4) == {'code': 'A', 'room_id': '100'}
        await invoke('watch B', group=5)
        await invoke('card', group=4)
        assert calls[-1] == ('A', '100')
        assert send_group.call_args.kwargs['group_id'] == 4
        assert await credit.get_balance('1') == 90
        await invoke('card', user=2, group=4)
        assert calls[-1] == ('A', '100')
        assert await credit.get_balance('2') == 20
        await invoke('card', user=1, group=5)
        assert calls[-1] == ('B', '200')
        assert send_group.call_args.kwargs['group_id'] == 5
        assert await credit.get_balance('1') == 80
        await invoke('watch BAD', group=4)
        assert app.service.watch_store.get(4)['code'] == 'A'
        assert app.service.watch_store.get(5)['code'] == 'B'
        assert await credit.get_balance('1') == 80
        count = len(calls)
        await invoke('card', user=3, group=4)
        assert len(calls) == count
        app.group_whitelist.add(7)
        await invoke('card', group=7)
        assert await credit.get_balance('1') == 80
        with patch.object(watch.WatchClient, 'fetch', side_effect=QueryError('对局已结束')):
            await invoke('card', group=4)
        assert await credit.get_balance('1') == 80
        with patch.object(app.rendering, 'render_hands', side_effect=ValueError('出图失败')):
            await invoke('card', group=4)
        assert await credit.get_balance('1') == 80
        with patch.object(app, 'send_image', new_callable=AsyncMock, return_value=False):
            await invoke('card', group=4)
        assert await credit.get_balance('1') == 80
        for call in send_group.call_args_list:
            payload = call.args[0].data['file']
            assert payload.startswith('base64://')
            picture = Image.open(io.BytesIO(base64.b64decode(payload[9:])))
            picture.load()
            assert picture.format == 'PNG'
        assert app.service.watch_store.get(4)['code'] == 'A'
        assert app.service.watch_store.get(5)['code'] == 'B'
        before_unwatch = charge.call_count
        before_fetch = len(calls)
        with patch.object(service, 'load_settings', side_effect=AssertionError('停止观战不应读取账号配置')):
            await invoke('unwatch', group=4)
        assert charge.call_count == before_unwatch
        assert await credit.get_balance('1') == 80
        assert app.service.watch_store.get(4) is None
        assert app.service.watch_store.get(5)['code'] == 'B'
        await invoke('card', group=4)
        assert len(calls) == before_fetch
        assert app.service.watch_store.get(4) is None
    await runtime.shutdown()
    print('群隔离、白名单、私聊拒绝、扣费退款与图片发送验证通过')

asyncio.run(main())
'''
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment['PYTHONPATH'] = str(ROOT)
            environment['PYTHONIOENCODING'] = 'utf-8'
            result = subprocess.run([sys.executable, '-c', program], cwd=directory, env=environment,
                                    capture_output=True, text=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('群隔离', result.stdout)
