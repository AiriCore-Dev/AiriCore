import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AstralPartyIntegrationTests(unittest.TestCase):
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

nonebot.init(_env_file=None, driver="~fastapi", command_start={"", "/"})
nonebot.get_driver().register_adapter(Adapter)
plugin = nonebot.load_plugin("plugins.airi_astral_party")
assert plugin is not None
app = plugin.module
from plugins.airi_astral_party import protocol as p, runtime

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

    for text in ("吉星帮助", "吉星绑定 123", "吉星状态", "吉星资料", "吉星无效"):
        verify(await app.prepare(text, "qq:1"))
    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    config = dict(host="127.0.0.1", port=server.sockets[0].getsockname()[1], game_id="test",
                  channel_id="test", app_id="test", sid="offline-test", device_id="test", cooldown=0)
    Path("data/astral_party/config.json").write_text(json.dumps(config), encoding="utf-8")
    try:
        for text in ("吉星资料", "吉星战绩", "吉星对局 1"):
            app.service._next_query = 0
            verify(await app.prepare(text, "qq:1"))
        assert calls == [5001, 5185, 5153] * 2 + [5001, 5185, 5153, 5155], calls
        event_data = dict(time=1, self_id=2, post_type="message", message_id=3, user_id=1,
                          message=Message("吉星帮助"), original_message=Message("吉星帮助"), raw_message="吉星帮助", font=0,
                          sender={"user_id": 1, "nickname": "测试"})
        private = PrivateMessageEvent(**event_data, message_type="private", sub_type="friend")
        group = GroupMessageEvent(**event_data, message_type="group", sub_type="normal", group_id=4)
        bot = AsyncMock()
        with patch.object(app, "send_group_with_fallback", new_callable=AsyncMock) as send_group:
            await app.handle(bot, private, ("吉星帮助",), Message())
            await app.handle(bot, group, ("吉星帮助",), Message())
            bot.send.assert_awaited_once()
            send_group.assert_awaited_once()
            assert send_group.call_args.kwargs["group_id"] == 4
            assert send_group.call_args.args[0].data["file"].startswith("base64://")
        verify(await app.prepare("吉星解绑", "qq:1"))
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
