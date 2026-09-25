import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AstralPartyIntegrationTests(unittest.TestCase):
    def test_bot_account_entry_scrubs_credentials_and_enforces_private_2fa(self):
        program = r'''
import asyncio
import base64
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import nonebot
from nonebot.adapters.onebot.v11 import Adapter, Message
from PIL import Image

nonebot.init(_env_file=None, driver='~fastapi', command_start={'', '/'}, nickname={'Airi', '小 Airi'}, superusers={'1'}, _2fa_key='JBSWY3DPEHPK3PXP')
nonebot.get_driver().register_adapter(Adapter)
plugin = nonebot.load_plugin('plugins.airi_astral_party')
assert plugin is not None
app = plugin.module
assert hasattr(app, 'accounts'), 'Bot 还未接入账号管理'
from plugins.airi_astral_party import bootstrap, renewal, runtime
from utils.superuser_2fa import superuser_2fa_preprocessor
from utils.observability import redact_astral_account_log

def event(raw, user=1, group=False):
    data = dict(time=1, self_id=2, post_type='message', message_id=3, user_id=user,
                message=[{'type': 'text', 'data': {'text': raw}}], raw_message=raw, font=0,
                sender={'user_id': user, 'nickname': '测试'},
                message_type='group' if group else 'private', sub_type='normal' if group else 'friend')
    if group:
        data['group_id'] = 4
    return Adapter.json_to_event(data)

async def main():
    bot = AsyncMock()
    for prefix in ('Airi ', 'Airi，', '小 Airi '):
        nick_event = event(prefix + '/astral 123456 account login 13800000000 private password&<文本>')
        assert '13800000000' not in nick_event.json(), '昵称前缀绕过了脱敏'
        assert nick_event._astral_credentials is not None
        assert nick_event._astral_credentials.digest == renewal.password_digest('private password&<文本>')
    for space in ('\r\n', '\u00a0', '\u3000', '\t'):
        for raw in (f'astral{space}123456 account{space}login 13800000000 private',
                    f'astral 123456 account{space}login{space}13800000000 private'):
            whitespace_event = event(raw)
            assert '13800000000' not in whitespace_event.model_dump_json(), '空白字符绕过脱敏'
            assert '13800000000' not in whitespace_event.get_plaintext()
    server = {'version': '3.2.1', 'route': '110001958', 'noticeUrl': '', 'serverUrl': 'se-jump-cn-01.feimogames.com:8800'}
    responses = []
    def transport(method, url, data=None):
        assert data['login_type'] == '19'
        assert data['tel_num'] == '13800000000'
        assert data['password'] == renewal.password_digest('private password&<文本>')
        responses.append(data['password'])
        return {'ret': 1, 'content': {'authorize_code': 'private-session', 'user_id': 'opaque-id'}}
    with patch.object(bootstrap, 'request_server', return_value=server), patch.object(renewal, 'request_json', side_effect=transport), patch('utils.superuser_2fa.totp_verify', side_effect=lambda secret, code: code == '123456'):
        for user, group, code in ((2, False, '123456'), (1, True, '123456'), (1, False, '654321'), (1, False, '123456')):
            current = event(f'/astral {code} account login 13800000000 private password&<文本>', user, group)
            assert current is not None
            for surface in (str(current), repr(current), current.json(), current.get_log_string(), str(current.original_message), current.raw_message):
                assert '13800000000' not in surface, surface
                assert 'private password' not in surface, surface
            await superuser_2fa_preprocessor(current)
            await app.handle(bot, current, ('astral',), Message('account login'))
            if user == 1 and not group and code == '123456':
                assert Path('data/astral_party/config.json').is_file()
            else:
                assert not Path('data/astral_party/config.json').exists()
        assert len(responses) == 1
        assert current._astral_credentials is None
        payload = bot.send.call_args.args[1].data['file']
        assert payload.startswith('base64://')
        picture = Image.open(io.BytesIO(base64.b64decode(payload[9:])))
        picture.load()
        assert picture.format == 'PNG'
        assert 'private password' not in Path('data/astral_party/config.json').read_text()
        assert bot.delete_msg.call_count >= 1
        for action in ('check', 'refresh', 'clear confirm'):
            current = event('astral 123456 account ' + action)
            await superuser_2fa_preprocessor(current)
            await app.handle(bot, current, ('astral',), Message('account ' + action))
        saved = json.loads(Path('data/astral_party/config.json').read_text())
        assert saved['sid'] == '' and saved['renewal'] == {}
        assert len(responses) == 2
    for message in ('收到 /astral 123456 account login 13800000000 private', '解析失败 astral account login\n13800000000\nprivate'):
        record = {'message': message, 'exception': RuntimeError('private')}
        redact_astral_account_log(record)
        assert 'private' not in record['message'] and '13800000000' not in record['message']
        assert record['exception'] is None
    harmless = {'message': 'astral 123 recent', 'exception': None}
    redact_astral_account_log(harmless)
    assert harmless['message'] == 'astral 123 recent'
    await runtime.shutdown()
    print('Bot 飞魔登录、权限、脱敏和清除验证通过')

asyncio.run(main())
'''
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment['PYTHONPATH'] = str(ROOT)
            environment['PYTHONIOENCODING'] = 'utf-8'
            result = subprocess.run([sys.executable, '-c', program], cwd=directory,
                                    env=environment, capture_output=True, text=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('权限', result.stdout)

    def test_isolated_nonebot_load_commands_tcp_and_base64(self):
        program = r'''
import asyncio
import base64
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import nonebot
from PIL import Image
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent, Message, PrivateMessageEvent
from nonebot.rule import TrieRule

nonebot.init(_env_file=None, driver="~fastapi", command_start={"", "/"})
nonebot.get_driver().register_adapter(Adapter)
plugin = nonebot.load_plugin("plugins.airi_astral_party")
assert plugin is not None
app = plugin.module
from plugins.airi_astral_party import protocol as p, runtime
from utils import credit
from utils.messaging import SendResult

async def main():
    calls = []
    tasks = set()
    async def serve(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        try:
            while True:
                frame = await p.read_frame(reader)
                calls.append(frame.command)
                if frame.command == 5001:
                    login = p.decode("ConnectC2S", frame.payload)
                    assert login.china.sid == "offline-test"
                    response = p.message("ConnectS2C", sessionId=90)
                    response.account.SetInParent()
                elif frame.command == 5185:
                    response = p.message("SearchPlayerS2C")
                    response.info.playerId = 123
                    response.info.name = "离线联调玩家"
                    response.info.lv = 12
                elif frame.command == 5153:
                    response = p.message("GetShowPlayerS2C")
                    response.showData.player_id = 123
                    response.showData.isShowData = True
                    response.showData.isShowFight = True
                    response.showData.statistics.fightCount = 10
                    response.showData.record.add(index=42, time=1750000000, rank=1, heroId=101, mapType=1)
                elif frame.command == 5155:
                    request = p.decode("GetPlayerFightRecordC2S", frame.payload)
                    assert request.index == 42
                    response = p.message("GetPlayerFightRecordS2C")
                    response.recordData.add(playerId=123, name="离线联调玩家", heroId=101, rank=1, lv=5, gold=30)
                else:
                    raise AssertionError(frame.command)
                writer.write(p.encode_frame(p.Frame(frame.command + 1, 90, frame.sequence, response.SerializeToString())))
                await writer.drain()
        except p.ProtocolError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    def verify(payload):
        picture = Image.open(io.BytesIO(payload))
        picture.load()
        assert picture.format == "PNG"
        segment = app.image_message(payload)
        assert segment.data["file"].startswith("base64://")
        assert base64.b64decode(segment.data["file"][9:]) == payload

    for text in ("astral help", "astral bind 123", "astral status", "astral me", "astral unknown"):
        verify(await app.prepare(text, "qq:1"))
    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    config = dict(host="127.0.0.1", port=server.sockets[0].getsockname()[1], game_id="test",
                  channel_id="test", app_id="test", sid="offline-test", device_id="test", cooldown=0)
    Path("data/astral_party/config.json").write_text(json.dumps(config), encoding="utf-8")
    try:
        for text in ("astral me", "astral me recent", "astral me battle 1"):
            app.service._next_query = 0
            verify(await app.prepare(text, "qq:1"))
        assert calls == [5001, 5185, 5153] * 2 + [5001, 5185, 5153, 5155], calls
        event_data = dict(time=1, self_id=2, post_type="message", message_id=3, user_id=1,
                          message=Message("astral help"), original_message=Message("astral help"), raw_message="astral help", font=0,
                          sender={"user_id": 1, "nickname": "测试"})
        private = PrivateMessageEvent(**event_data, message_type="private", sub_type="friend")
        group = GroupMessageEvent(**event_data, message_type="group", sub_type="normal", group_id=4)
        bot = AsyncMock()
        for raw, expected in (
            ("astral", True), ("astral help", True), ("/astral me", True),
            ("astral 123 recent", True), ("astral me recent 2", True),
            ("astral me battle 1", True), ("astral 123 battle 1", True),
            ("astral status", True), ("astral bind 123", True), ("astral unbind", True),
            ("astralhelp", False), ("astral123", False), ("吉星帮助", False), ("吉星资料 123", False),
        ):
            candidate = PrivateMessageEvent(
                **{**event_data, "message": Message(raw), "original_message": Message(raw), "raw_message": raw},
                message_type="private", sub_type="friend",
            )
            state = {}
            TrieRule.get_value(bot, candidate, state)
            assert await app.matcher.rule(bot, candidate, state) == expected, raw
        with patch.object(app, "send_group_with_fallback", new_callable=AsyncMock) as send_group:
            await app.handle(bot, private, ("astral",), Message("help"))
            await app.handle(bot, group, ("astral",), Message("help"))
            bot.send.assert_awaited_once()
            send_group.assert_awaited_once()
            assert send_group.call_args.kwargs["group_id"] == 4
            assert send_group.call_args.args[0].data["file"].startswith("base64://")
        assert not await credit.has_account('1')
        await credit.credit('1', 35)
        for index, command in enumerate(('123', 'me recent', '123 battle 1')):
            app.service._next_query = 0
            await app.handle(bot, private, ('astral',), Message(command))
            assert await credit.get_balance('1') == 35 - (index + 1) * 10, '每次查询应扣除 10 积分'
        previous_calls = len(calls)
        app.service._next_query = 0
        await app.handle(bot, private, ('astral',), Message('123'))
        assert len(calls) == previous_calls, '余额不足不应发起查询'
        assert await credit.get_balance('1') == 5
        await credit.credit('1', 25)
        for command in ('help', 'bind 123', 'status', 'unknown', '123 recent 99', 'unbind', 'me'):
            await app.handle(bot, private, ('astral',), Message(command))
            assert await credit.get_balance('1') == 30, command
        for command in ('123 recent 2', '123 battle 2'):
            app.service._next_query = 0
            await app.handle(bot, private, ('astral',), Message(command))
            assert await credit.get_balance('1') == 30, '查询失败应退款'
        app.service._next_query = float('inf')
        await app.handle(bot, private, ('astral',), Message('123'))
        assert await credit.get_balance('1') == 30, '冷却拒绝应退款'
        app.service._next_query = 0
        with patch.object(app.rendering, 'render_profile', side_effect=RuntimeError('测试出图失败')):
            await app.handle(bot, private, ('astral',), Message('123'))
        assert await credit.get_balance('1') == 30, '出图失败应退款'
        app.service._next_query = 0
        bot.send.side_effect = RuntimeError('测试发送失败')
        try:
            await app.handle(bot, private, ('astral',), Message('123'))
        except RuntimeError:
            pass
        bot.send.side_effect = None
        assert await credit.get_balance('1') == 30, '私聊发送失败应退款'
        for success in (False, True):
            app.service._next_query = 0
            with patch.object(app, 'send_group_with_fallback', new_callable=AsyncMock,
                              return_value=SendResult(success, '2', None)):
                await app.handle(bot, group, ('astral',), Message('123'))
            assert await credit.get_balance('1') == (20 if success else 30), '按群消息实际发送结果计费'
        started, release = asyncio.Event(), asyncio.Event()
        async def delayed_send(*args):
            started.set()
            await release.wait()
        bot.send.side_effect = delayed_send
        app.service._next_query = 0
        operation = asyncio.create_task(app.handle(bot, private, ('astral',), Message('123')))
        await asyncio.wait_for(started.wait(), 10)
        operation.cancel()
        release.set()
        try:
            await operation
        except asyncio.CancelledError:
            pass
        assert await credit.get_balance('1') == 10, '取消等待后仍成功送达的查询只能扣费一次'
        await credit.reset_for_tests()
        assert await credit.get_balance('1') == 10, '扣费结果应持久保存'
        verify(await app.prepare("astral unbind", "qq:1"))
    finally:
        server.close()
        await server.wait_closed()
        if tasks:
            await asyncio.gather(*tuple(tasks))
        await runtime.shutdown()
    assert not runtime._pending
    print("离线插件加载、TCP 查询、命令出图与 Base64 发送验证通过")

asyncio.run(main())
'''
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment['PYTHONPATH'] = str(ROOT)
            environment['PYTHONIOENCODING'] = 'utf-8'
            result = subprocess.run([sys.executable, '-c', program], cwd=directory,
                                    env=environment, capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Base64', result.stdout)
