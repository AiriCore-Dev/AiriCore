import asyncio
import importlib
import json
import struct
import sys
import types
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_astral_party_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'plugins/airi_astral_party')]
sys.modules[PACKAGE] = package


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p = importlib.import_module(f'{PACKAGE}.protocol')

    def test_original_fixed_width_player_id(self):
        payload = self.p.message('SearchPlayerC2S', playerId=123456789).SerializeToString()
        self.assertEqual(payload, b'\x09' + struct.pack('<q', 123456789))
        request = self.p.message('GetPlayerFightRecordC2S', player_id=123, index=17)
        self.assertEqual(request.SerializeToString(), b'\x09' + struct.pack('<q', 123) + b'\x15' + struct.pack('<i', 17))

    async def test_fragmented_and_consecutive_frames(self):
        reader = asyncio.StreamReader()
        frame = self.p.Frame(5154, 42, 101, b'\x01\x02')
        packet = self.p.encode_frame(frame)
        self.assertEqual(len(packet), 37)
        self.assertEqual(packet[:17], struct.pack('>IqHBBB', 2, 42, 5154, 1, 0, 0))
        pending = asyncio.create_task(self.p.read_frame(reader))
        reader.feed_data(packet[:9])
        await asyncio.sleep(0)
        self.assertFalse(pending.done())
        reader.feed_data(packet[9:] + packet)
        self.assertEqual(await pending, frame)
        self.assertEqual(await self.p.read_frame(reader), frame)

    async def test_frame_limits_and_truncation(self):
        for size in (-1, self.p.MAX_PAYLOAD + 1):
            reader = asyncio.StreamReader()
            reader.feed_data(struct.pack('>iqHBBBqqH', size, 0, 5002, 1, 0, 0, 1, 0, 0))
            with self.assertRaises(self.p.ProtocolError):
                await self.p.read_frame(reader)
        reader = asyncio.StreamReader()
        reader.feed_data(b'\x00')
        reader.feed_eof()
        with self.assertRaises(self.p.ProtocolError):
            await self.p.read_frame(reader)

    def test_unknown_fields_and_malformed_protobuf(self):
        data = self.p.message('GetShowPlayerS2C')
        data.showData.player_id = 123
        payload = data.SerializeToString() + b'\xa0\x06\x01'
        self.assertEqual(self.p.decode('GetShowPlayerS2C', payload).showData.player_id, 123)
        with self.assertRaises(self.p.ProtocolError):
            self.p.decode('GetShowPlayerS2C', b'\x0a\xff')


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p = importlib.import_module(f'{PACKAGE}.protocol')
        self.c = importlib.import_module(f'{PACKAGE}.client')
        self.settings = importlib.import_module(f'{PACKAGE}.settings')
        self.commands = []
        self.fail = 0
        self.hidden = False
        self.wrong_sequence = False
        self.handlers = set()
        self.server = await asyncio.start_server(self.serve, '127.0.0.1', 0)
        self.config = self.settings.Settings(host='127.0.0.1', port=self.server.sockets[0].getsockname()[1],
                                             game_id='test', channel_id='test', app_id='test', sid='offline-test',
                                             device_id='test', timeout=0.2)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        if self.handlers:
            await asyncio.gather(*tuple(self.handlers), return_exceptions=True)

    async def serve(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        try:
            while True:
                frame = await self.p.read_frame(reader)
                self.commands.append(frame.command)
                if frame.command == 5001:
                    login = self.p.decode('ConnectC2S', frame.payload)
                    self.assertEqual(login.auth, 4)
                    self.assertEqual(login.china.sid, 'offline-test')
                    response = self.p.message('ConnectS2C', sessionId=900)
                    response.account.SetInParent()
                elif frame.command == 5185:
                    self.assertEqual(frame.session, 900)
                    response = self.p.message('SearchPlayerS2C')
                    response.info.playerId = 123456789
                    response.info.name = '测试玩家'
                    response.info.lv = 25
                elif frame.command == 5153:
                    response = self.p.message('GetShowPlayerS2C')
                    response.showData.player_id = 123456789
                    response.showData.isShowData = not self.hidden
                    response.showData.isShowFight = not self.hidden
                    response.showData.statistics.fightCount = 10
                    response.showData.statistics.winFightCount = 2
                    response.showData.record.add(index=87, time=100, heroId=101, rank=1)
                elif frame.command == 5155:
                    request = self.p.decode('GetPlayerFightRecordC2S', frame.payload)
                    self.assertEqual(request.index, 87)
                    self.assertFalse(request.isReplay)
                    response = self.p.message('GetPlayerFightRecordS2C')
                    response.recordData.add(playerId=123456789, name='测试玩家', rank=1, heroId=101)
                else:
                    self.failures = frame.command
                    return
                push = self.p.encode_frame(self.p.Frame(5004, 900, 0, b''))
                payload = self.p.encode_frame(self.p.Frame(frame.command + 1, 900,
                    frame.sequence + (1 if self.wrong_sequence else 0), response.SerializeToString(), self.fail))
                writer.write(push + payload[:8])
                await writer.drain()
                await asyncio.sleep(0)
                writer.write(payload[8:])
                await writer.drain()
        except self.p.ProtocolError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            self.handlers.discard(task)

    async def test_real_tcp_transaction_and_detail_index(self):
        result = await self.c.GameClient(self.config).fetch(123456789, detail=1)
        self.assertEqual(self.commands, [5001, 5185, 5153, 5155])
        self.assertEqual(result['info']['name'], '测试玩家')
        self.assertEqual(result['details'][0]['rank'], 1)

    async def test_hidden_data_is_removed_and_detail_not_requested(self):
        self.hidden = True
        client = self.c.GameClient(self.config)
        result = await client.fetch(123456789)
        self.assertEqual(result['show']['record'], [])
        self.assertNotIn('statistics', result['show'])
        with self.assertRaisesRegex(self.p.QueryError, '未公开'):
            await client.fetch(123456789, detail=1)
        self.assertNotIn(5155, self.commands)

    async def test_login_error_stops_before_query(self):
        self.fail = 10003
        with self.assertRaisesRegex(self.p.QueryError, '10003'):
            await self.c.GameClient(self.config).fetch(123456789)
        self.assertEqual(self.commands, [5001])

    async def test_wrong_response_sequence_times_out(self):
        self.wrong_sequence = True
        with self.assertRaisesRegex(self.p.QueryError, '超时'):
            await self.c.GameClient(self.config).fetch(123456789)

    async def test_unconfigured_does_not_connect(self):
        with self.assertRaisesRegex(self.p.QueryError, '配置'):
            await self.c.GameClient(self.settings.Settings()).fetch(123456789)
        self.assertEqual(self.commands, [])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.s = importlib.import_module(f'{PACKAGE}.settings')

    def test_secrets_are_not_in_repr(self):
        self.assertNotIn('secret-value', repr(self.s.Settings(sid='secret-value')))

    def test_invalid_configuration_never_echoes_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text('{"sid":"secret-value", "port":"secret-value"}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '配置') as error:
                self.s.load_settings(path)
            self.assertNotIn('secret-value', str(error.exception))


class CommandAndStorageTests(unittest.TestCase):
    def setUp(self):
        self.s = importlib.import_module(f'{PACKAGE}.service')

    def test_astral_command_forms(self):
        cases = {
            'astral': ('帮助', None, 1),
            'astral help': ('帮助', None, 1),
            'astral bind 123456789': ('绑定', 123456789, 1),
            'astral unbind': ('解绑', None, 1),
            'astral status': ('状态', None, 1),
            'astral me': ('资料', None, 1),
            'astral 123456789': ('资料', 123456789, 1),
            'astral me recent': ('战绩', None, 1),
            'astral me recent 2': ('战绩', None, 2),
            'astral 123456789 recent': ('战绩', 123456789, 1),
            'astral 123456789 recent 2': ('战绩', 123456789, 2),
            'astral me battle 3': ('对局', None, 3),
            'astral 123456789 battle 3': ('对局', 123456789, 3),
            ' astral   me\trecent  2 ': ('战绩', None, 2),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                command = self.s.parse_command(text)
                self.assertEqual((command.action, command.uid, command.number), expected)

    def test_invalid_parameters(self):
        for text in ('astral bind -1', 'astral 0', 'astral 9223372036854775808',
                     'astral me battle', 'astral unbind 123', 'astral 123 recent 0',
                     'astral bind 1 2', 'astral me recent 21', 'astral me battle 101',
                     'astral recent', 'astral battle 1', 'astral help 1', 'astral status 1',
                     'astral me 2', 'astral me recent 第2页', 'astral123', 'me', '',
                     '吉星资料 123', '吉星帮助', 'astral me recent 2 3', 'astral ' + '9' * 1000):
            with self.subTest(text=text[:50]), self.assertRaises(ValueError):
                self.s.parse_command(text)

    def test_atomic_binding_round_trip_and_user_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bindings.json'
            store = self.s.BindingStore(path)
            store.set('qq:1', 123)
            store.set('qq:2', 456)
            self.assertEqual(self.s.BindingStore(path).get('qq:1'), 123)
            with patch(f'{PACKAGE}.service.os.replace', side_effect=OSError):
                with self.assertRaises(ValueError):
                    store.set('qq:1', 789)
            self.assertEqual(store.get('qq:1'), 123)
            store.set('qq:1', None)
            self.assertIsNone(store.get('qq:1'))
            self.assertEqual(store.get('qq:2'), 456)
            self.assertFalse(list(Path(directory).glob('*.tmp')))

    def test_corrupt_bindings_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bindings.json'
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '损坏'):
                self.s.BindingStore(path).set('qq:1', 123)
            self.assertEqual(path.read_text(encoding='utf-8'), '{broken')


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_me_requires_binding_and_explicit_uid_does_not(self):
        service = importlib.import_module(f'{PACKAGE}.service')
        settings = importlib.import_module(f'{PACKAGE}.settings')
        with tempfile.TemporaryDirectory() as directory:
            app = service.QueryService(Path(directory))
            fake = AsyncMock()
            fake.fetch.return_value = {'show': {'record': [{}]}}
            with patch(f'{PACKAGE}.service.load_settings', return_value=settings.Settings(cooldown=0)), \
                 patch(f'{PACKAGE}.service.GameClient', return_value=fake):
                for command in ('astral me', 'astral me recent', 'astral me battle 1'):
                    with self.assertRaisesRegex(ValueError, 'astral bind UID'):
                        await app.handle(command, 'qq:1')
                fake.fetch.assert_not_awaited()
                await app.handle('astral 123', 'qq:1')
                fake.fetch.assert_awaited_once_with(123, detail=None)
                await app.handle('astral bind 456', 'qq:1')
                await app.handle('astral me battle 1', 'qq:1')
                fake.fetch.assert_awaited_with(456, detail=1)
                await app.handle('astral unbind', 'qq:1')
                with self.assertRaisesRegex(ValueError, 'astral bind UID'):
                    await app.handle('astral me', 'qq:1')

    async def test_page_boundaries(self):
        service = importlib.import_module(f'{PACKAGE}.service')
        settings = importlib.import_module(f'{PACKAGE}.settings')
        for count in (0, 6, 7, 12, 13):
            for page in range(1, 5):
                with self.subTest(count=count, page=page), tempfile.TemporaryDirectory() as directory:
                    app = service.QueryService(Path(directory))
                    fake = AsyncMock()
                    fake.fetch.return_value = {'show': {'record': [{}] * count}}
                    with patch(f'{PACKAGE}.service.load_settings', return_value=settings.Settings(cooldown=0)), \
                         patch(f'{PACKAGE}.service.GameClient', return_value=fake):
                        if (page - 1) * 6 < max(1, count):
                            result = await app.handle(f'astral 123 recent {page}', 'qq:1')
                            self.assertEqual(result['page'], page)
                        else:
                            with self.assertRaisesRegex(ValueError, '该战绩页不存在'):
                                await app.handle(f'astral 123 recent {page}', 'qq:1')

    async def test_binding_help_and_missing_configuration(self):
        service = importlib.import_module(f'{PACKAGE}.service')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = service.QueryService(root)
            result = await app.handle('astral help', 'qq:1')
            self.assertEqual(result['kind'], 'help')
            result = await app.handle('astral bind 123456789', 'qq:1')
            self.assertEqual(result['kind'], 'notice')
            with self.assertRaisesRegex(ValueError, '配置'):
                await app.handle('astral me', 'qq:1')
            with self.assertRaisesRegex(ValueError, '绑定'):
                await app.handle('astral me', 'qq:2')

    async def test_command_to_snapshot_and_global_cooldown(self):
        service = importlib.import_module(f'{PACKAGE}.service')
        settings = importlib.import_module(f'{PACKAGE}.settings')
        snapshot = {'uid': 123, 'info': {}, 'show': {'record': []}, 'details': [], 'selected': None}
        with tempfile.TemporaryDirectory() as directory:
            app = service.QueryService(Path(directory))
            fake = AsyncMock()
            fake.fetch.return_value = snapshot
            with patch(f'{PACKAGE}.service.load_settings', return_value=settings.Settings(cooldown=10)), \
                 patch(f'{PACKAGE}.service.GameClient', return_value=fake):
                result = await app.handle('astral 123', 'qq:1')
                self.assertEqual(result['kind'], 'profile')
                self.assertEqual(result['snapshot'], snapshot)
                with self.assertRaisesRegex(ValueError, '稍后'):
                    await app.handle('astral 456', 'qq:2')
                fake.fetch.assert_awaited_once_with(123, detail=None)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtime = importlib.import_module(f'{PACKAGE}.runtime')
        self.runtime._closing = False
        self.runtime._render_lock = asyncio.Lock()

    async def test_maintenance_starts_once_and_shutdown_drains_inflight_write(self):
        import threading
        loop = asyncio.get_running_loop()
        started, release = asyncio.Event(), threading.Event()
        completed = threading.Event()

        def write():
            loop.call_soon_threadsafe(started.set)
            release.wait(timeout=3)
            completed.set()

        async def maintain():
            await self.runtime.run_sync(write)

        first = self.runtime.start_maintenance(maintain)
        self.assertIs(first, self.runtime.start_maintenance(maintain))
        await asyncio.wait_for(started.wait(), 2)
        closing = asyncio.create_task(self.runtime.shutdown())
        try:
            await asyncio.sleep(0)
            self.assertFalse(closing.done())
        finally:
            release.set()
        await asyncio.wait_for(closing, 3)
        self.assertTrue(completed.is_set())
        self.assertTrue(first.done())

    async def test_shutdown_drains_operation_and_rejects_new_work(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def work():
            started.set()
            await release.wait()
            return 123

        operation = asyncio.create_task(self.runtime.run_operation(work()))
        await started.wait()
        closing = asyncio.create_task(self.runtime.shutdown())
        await asyncio.sleep(0)
        self.assertFalse(closing.done())
        with self.assertRaisesRegex(ValueError, '关闭'):
            await self.runtime.run_operation(work())
        release.set()
        self.assertEqual(await operation, 123)
        await closing
        self.assertFalse(self.runtime._pending)

    async def test_cancelled_render_waits_for_executor(self):
        import threading
        loop = asyncio.get_running_loop()
        started, release = asyncio.Event(), threading.Event()
        completed = threading.Event()

        def work():
            loop.call_soon_threadsafe(started.set)
            release.wait(timeout=3)
            completed.set()

        task = asyncio.create_task(self.runtime.run_sync(work))
        try:
            await started.wait()
            task.cancel()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertFalse(completed.is_set())
        finally:
            release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(completed.is_set())
