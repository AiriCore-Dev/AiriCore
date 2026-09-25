import asyncio
import importlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_astral_watch_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'plugins/airi_astral_party')]
sys.modules[PACKAGE] = package


class WatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p = importlib.import_module(f'{PACKAGE}.protocol')
        self.service = importlib.import_module(f'{PACKAGE}.service')
        self.settings = importlib.import_module(f'{PACKAGE}.settings')

    async def test_commands_include_group_watch_and_card(self):
        try:
            command = self.service.parse_command('astral watch ABC-123')
        except self.p.QueryError as error:
            self.fail(f'观战指令尚未实现：{error}')
        self.assertEqual(command.action, '观战')
        self.assertEqual(command.watch_code, 'ABC-123')
        self.assertEqual(self.service.parse_command('astral card').action, '手牌')
        self.assertEqual(self.service.parse_command('astral unwatch').action, '停止观战')
        for text in ('astral watch', 'astral watch A B', 'astral card A', 'astral unwatch A',
                     'astral watch ' + 'a' * 65):
            with self.subTest(text=text), self.assertRaises(self.p.QueryError):
                self.service.parse_command(text)

    async def test_groups_are_persistent_independent_and_failed_watch_preserves_target(self):
        self.assertTrue(hasattr(self.service.QueryService, 'handle_watch'), '群观战服务尚未实现')
        watch = importlib.import_module(f'{PACKAGE}.watch')
        with tempfile.TemporaryDirectory() as directory:
            service = self.service.QueryService(directory)
            calls = []
            async def fetch(code, expected_room=None):
                calls.append((code, expected_room))
                if code == 'bad':
                    raise self.p.QueryError('观战码无效')
                return {'room_id': '100' if code == 'A' else '200', 'round': 1, 'players': []}
            with patch.object(self.service, 'load_settings', return_value=self.settings.Settings(cooldown=0)), \
                 patch.object(watch.WatchClient, 'fetch', side_effect=fetch):
                for text in ('astral watch A', 'astral card'):
                    with self.assertRaisesRegex(self.p.QueryError, '群聊'):
                        await service.handle(text, 'qq:1')
                self.assertEqual(calls, [])
                await service.handle('astral watch A', 'qq:1', group=10)
                await service.handle('astral watch B', 'qq:1', group=20)
                first = await service.handle('astral card', 'qq:2', group=10)
                second = await service.handle('astral card', 'qq:1', group=20)
                self.assertEqual(first['kind'], 'hands')
                self.assertEqual(first['snapshot']['room_id'], '100')
                self.assertEqual(second['snapshot']['room_id'], '200')
                self.assertEqual(first['snapshot']['watch_code'], 'A')
                self.assertEqual(second['snapshot']['watch_code'], 'B')
                with self.assertRaisesRegex(self.p.QueryError, '先.*watch'):
                    await service.handle('astral card', 'qq:1', group=30)
                with self.assertRaises(self.p.QueryError):
                    await service.handle('astral watch bad', 'qq:1', group=10)
                restarted = self.service.QueryService(directory)
                await restarted.handle('astral card', 'qq:3', group=10)
                self.assertEqual(calls[-1], ('A', '100'))
                async with service._lock:
                    with self.assertRaisesRegex(self.p.QueryError, '频繁|稍后'):
                        await service.handle('astral card', 'qq:1', group=10)

    async def test_unwatch_needs_group_but_not_settings_or_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service.QueryService(directory)
            service.watch_store.set(10, 'A', '100')
            service.watch_store.set(20, 'B', '200')
            service._next_query = float('inf')
            with patch.object(self.service, 'load_settings', side_effect=AssertionError('不应读取账号配置')):
                with self.assertRaisesRegex(self.p.QueryError, '群聊'):
                    await service.handle('astral unwatch', 'qq:1')
                view = await service.handle('astral unwatch', 'qq:1', group=10)
                self.assertEqual(view['kind'], 'notice')
                self.assertIsNone(service.watch_store.get(10))
                self.assertEqual(service.watch_store.get(20), {'code': 'B', 'room_id': '200'})
                await service.handle('astral unwatch', 'qq:1', group=10)
            restarted = self.service.QueryService(directory)
            self.assertIsNone(restarted.watch_store.get(10))
            self.assertEqual(restarted.watch_store.get(20)['code'], 'B')

    async def test_unwatch_waits_for_active_watch_and_remains_removed(self):
        watch = importlib.import_module(f'{PACKAGE}.watch')
        with tempfile.TemporaryDirectory() as directory:
            service = self.service.QueryService(directory)
            started = asyncio.Event()
            release = asyncio.Event()
            async def fetch(code, expected_room=None):
                started.set()
                await release.wait()
                return {'room_id': '100', 'round': 1, 'players': []}
            with patch.object(self.service, 'load_settings', return_value=self.settings.Settings(cooldown=0)), \
                 patch.object(watch.WatchClient, 'fetch', side_effect=fetch):
                active = asyncio.create_task(service.handle('astral watch A', 'qq:1', group=10))
                await started.wait()
                stopped = asyncio.create_task(service.handle('astral unwatch', 'qq:1', group=10))
                await asyncio.sleep(0)
                self.assertFalse(stopped.done())
                release.set()
                await active
                await stopped
                self.assertIsNone(service.watch_store.get(10))


class WatchStoreTests(unittest.TestCase):
    def test_atomic_storage_rejects_corruption_and_preserves_other_groups(self):
        module_path = ROOT / 'plugins/airi_astral_party/watch_store.py'
        self.assertTrue(module_path.exists(), '群观战存储尚未实现')
        module = importlib.import_module(f'{PACKAGE}.watch_store')
        error = importlib.import_module(f'{PACKAGE}.protocol').QueryError
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'watch.json'
            store = module.GroupWatchStore(path)
            self.assertIsNone(store.get(1))
            store.set(1, 'AAA', '100')
            module.GroupWatchStore(path).set(2, 'BBB', '200')
            self.assertEqual(store.get('01'), {'code': 'AAA', 'room_id': '100'})
            self.assertEqual(store.get(2)['code'], 'BBB')
            self.assertTrue(store.delete(1))
            self.assertFalse(store.delete(1))
            self.assertIsNone(module.GroupWatchStore(path).get(1))
            self.assertEqual(store.get(2)['code'], 'BBB')
            store.set(1, 'AAA', '100')
            original = path.read_bytes()
            with patch.object(module.os, 'replace', side_effect=OSError('写入失败')):
                with self.assertRaises(error):
                    store.set(1, 'CCC', '300')
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob('*.tmp')), [])
            with patch.object(module.os, 'replace', side_effect=OSError('写入失败')):
                with self.assertRaises(error):
                    store.delete(1)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob('*.tmp')), [])
            for value in ('{坏档', '[]', '{"1":{"code":"x","room_id":true}}',
                          '{"1":{"code":"x","room_id":"0"}}'):
                path.write_text(value, encoding='utf-8')
                with self.assertRaises(error):
                    store.get(1)
                with self.assertRaises(error):
                    store.set(2, 'B', '200')
                with self.assertRaises(error):
                    store.delete(1)
                self.assertEqual(path.read_text(encoding='utf-8'), value)


class CardStateTests(unittest.TestCase):
    def test_cost_respects_battle_override_mode_and_skill_buff(self):
        state = importlib.import_module(f'{PACKAGE}.card_state').card_state
        card = {'id': 10007, 'cost': 2, 'purify': 0}
        player = {'card_attack_bonus': 0, 'card_distance_bonus': 0, 'buffs': []}
        self.assertEqual(state(card, player, 4)['cost'], 2)
        self.assertEqual(state(card, player, 10)['cost'], 4)
        player['buffs'] = [{'id': 1151201, 'progress': 0, 'chain': [{'source': 1, 'id': 11512}]}]
        self.assertEqual(state(card, player, 4)['cost'], 1)
        self.assertEqual(state(card, player, 10)['cost'], 1)
        self.assertEqual(state({'id': 10007, 'cost': -1}, player, 4)['cost'], 3)
        player['buffs'][0]['chain'].insert(0, {'source': 2, 'id': 1})
        self.assertEqual(state(card, player, 4)['cost'], 2)
        self.assertEqual(state(card, player, 10)['cost'], 4)

    def test_description_uses_client_range_damage_and_purify_rules(self):
        state = importlib.import_module(f'{PACKAGE}.card_state').card_state
        player = {'card_attack_bonus': 2, 'card_distance_bonus': 3, 'buffs': []}
        result = state({'id': 20001, 'cost': 0}, player, 4)['description']
        self.assertIn('{range=[color=#94FF46]9[/color]}', result)
        self.assertIn('{damage=[color=#94FF46]5[/color]}', result)
        result = state({'id': 21019, 'cost': 0}, player, 4)['description']
        self.assertIn('{range=[color=#94FF46]9[/color]}', result)
        self.assertIn('{damage=3}', result)
        player['buffs'] = [{'id': 1211201, 'progress': 4, 'chain': []}]
        result = state({'id': 20031, 'cost': 0}, player, 4)['description']
        self.assertIn('{damage=[color=#94FF46]8[/color]}', result)
        result = state({'id': 21022, 'cost': 0, 'purify': 2}, player, 4)['description']
        self.assertIn('{stack=[color=#94FF46]2[/color]}', result)
        self.assertNotIn('{damage=', result)


class WatchClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p = importlib.import_module(f'{PACKAGE}.protocol')
        self.settings = importlib.import_module(f'{PACKAGE}.settings')
        self.commands = []
        self.handlers = set()
        self.errors = {}
        self.wrong_room = False
        self.top_room_id = 100
        self.join_map_type = 4
        self.snapshot_map_type = 4
        self.decorate = False
        self.ended = False
        self.delay_refresh = False
        self.refresh_seen = asyncio.Event()
        self.server = await asyncio.start_server(self.serve, '127.0.0.1', 0)
        self.config = self.settings.Settings(host='127.0.0.1', port=self.server.sockets[0].getsockname()[1],
            game_id='test', channel_id='test', app_id='test', sid='test', device_id='test', timeout=0.2)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        if self.handlers:
            await asyncio.gather(*tuple(self.handlers), return_exceptions=True)

    def client(self):
        self.assertTrue((ROOT / 'plugins/airi_astral_party/watch.py').exists(), '观战协议客户端尚未实现')
        return importlib.import_module(f'{PACKAGE}.watch').WatchClient(self.config)

    async def serve(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        try:
            while True:
                frame = await self.p.read_frame(reader)
                self.commands.append(frame.command)
                if frame.command == 5001:
                    response = self.p.message('ConnectS2C', sessionId=900)
                    response.account.SetInParent()
                elif frame.command == 5191:
                    request = self.p.decode('WatchJoinRoomC2S', frame.payload)
                    self.assertEqual(request.watchCode, 'ABC123')
                    self.assertEqual(frame.session, 900)
                    response = self.p.message('WatchJoinRoomS2C', room_id=100, room_server_id=7, map_type=self.join_map_type)
                elif frame.command == 5193:
                    request = self.p.decode('WatchRefreshRoomStateC2S', frame.payload)
                    self.assertEqual((request.room_id, request.room_server_id), (100, 7))
                    response = self.p.message('WatchRefreshRoomStateS2C', room_id=self.top_room_id)
                    room = response.room
                    room.id = 200 if self.wrong_room else 100
                    room.state = 0 if self.ended else 25
                    room.mapType = self.snapshot_map_type
                    room.round = 3
                    for slot in range(4):
                        player = room.players.add(id=slot + 1, nick=f'测试玩家{slot}', slot=slot)
                        player.hero.hero_id = 101 + slot
                        player.hero.cards.add(uniqueId=1, cardId=21001)
                        player.hero.cards.add(uniqueId=2, cardId=-34 if slot else 21002)
                        if self.decorate and slot == 0:
                            player.fashionPlan.add().fashion[3] = 100777
                            player.altArtCards[999].cardId = 21001
                            player.altArtCards[999].cardFaceId = 91001
                            player.hero.cardAtk = 2
                            player.hero.cardDistance = 1
                            player.hero.addition_attrs[8].cardAtk = 3
                            player.hero.addition_attrs[9].cardDistance = 2
                            player.hero.buffs[44].buff_id = 1211201
                            player.hero.buffs[44].progress = 4
                            player.hero.buffs[45].buff_id = 1151201
                            player.hero.buffs[45].chain.add(s=1, id=7001)
                        player.token = '不应泄漏的玩家数据'
                    self.refresh_seen.set()
                    if self.delay_refresh:
                        continue
                elif frame.command == 5195:
                    response = self.p.message('WatchExitRoomS2C')
                else:
                    raise AssertionError(f'意外请求 {frame.command}')
                push = self.p.encode_frame(self.p.Frame(1109, 900, 0, b''))
                packet = self.p.encode_frame(self.p.Frame(frame.command + 1, 900, frame.sequence,
                    response.SerializeToString(), self.errors.get(frame.command, 0), version=(2, 0, 0)))
                writer.write(push + packet[:8])
                await writer.drain()
                await asyncio.sleep(0)
                writer.write(packet[8:])
                await writer.drain()
        except (self.p.ProtocolError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            self.handlers.discard(task)

    async def test_snapshot_uses_observer_flow_and_strips_unrelated_account_fields(self):
        result = await self.client().fetch('ABC123')
        self.assertEqual(self.commands, [5001, 5191, 5193, 5195])
        self.assertEqual((result['room_id'], result['round'], len(result['players'])), ('100', 3, 4))
        self.assertGreater(result['captured_at'], 0)
        self.assertEqual(result['players'][1]['cards'][1]['id'], None)
        self.assertEqual(result['players'][0]['cards'][0]['id'], 21001)
        self.assertNotIn('token', json.dumps(result))
        self.assertNotIn('不应泄漏', json.dumps(result, ensure_ascii=False))

    async def test_snapshot_includes_visible_card_context(self):
        self.decorate = True
        result = await self.client().fetch('ABC123')
        player = result['players'][0]
        self.assertEqual(player['card_back_item_id'], 100777)
        self.assertEqual(player['card_attack_bonus'], 5)
        self.assertEqual(player['card_distance_bonus'], 3)
        self.assertEqual(player['cards'][0]['alt_art_id'], 91001)
        self.assertIsNone(player['cards'][1]['alt_art_id'])
        self.assertEqual(player['buffs'][0]['id'], 1151201)
        self.assertEqual(player['buffs'][0]['chain'], [{'source': 1, 'id': 7001}])
        self.assertEqual(player['buffs'][1]['id'], 1211201)
        self.assertEqual(player['buffs'][1]['progress'], 4)
        self.assertIsNone(result['players'][1]['card_back_item_id'])
        self.assertNotIn('999', json.dumps(result))

    async def test_room_reuse_does_not_query_new_room_and_exits(self):
        with self.assertRaisesRegex(self.p.QueryError, '对局|房间'):
            await self.client().fetch('ABC123', expected_room='99')
        self.assertEqual(self.commands, [5001, 5191, 5195])

    async def test_pvp_join_is_rejected_before_refresh_and_exits(self):
        self.join_map_type = 1
        with self.assertRaisesRegex(self.p.QueryError, 'PVP|PVE|玩家对战'):
            await self.client().fetch('ABC123')
        self.assertEqual(self.commands, [5001, 5191, 5195])

    async def test_pvp_snapshot_is_rejected_and_exits(self):
        self.snapshot_map_type = 3
        with self.assertRaisesRegex(self.p.QueryError, 'PVP|PVE|玩家对战'):
            await self.client().fetch('ABC123', expected_room='100')
        self.assertEqual(self.commands, [5001, 5191, 5193, 5195])

    async def test_omitted_outer_room_id_uses_verified_inner_room(self):
        self.top_room_id = 0
        result = await self.client().fetch('ABC123', expected_room='100')
        self.assertEqual(result['room_id'], '100')
        self.wrong_room = True
        with self.assertRaises(self.p.QueryError):
            await self.client().fetch('ABC123', expected_room='100')
        self.wrong_room = False
        self.top_room_id = 101
        with self.assertRaises(self.p.QueryError):
            await self.client().fetch('ABC123', expected_room='100')

    async def test_observer_errors_have_specific_chinese_messages(self):
        for code, text in ((11001, '房间不存在'), (11080, '结束'), (11081, '观战码'), (11082, '人数')):
            self.errors = {5191: code}
            with self.subTest(code=code), self.assertRaisesRegex(self.p.QueryError, text):
                await self.client().fetch('ABC123')

    async def test_bad_snapshot_and_game_end_are_rejected_and_exit(self):
        self.wrong_room = True
        with self.assertRaises(self.p.QueryError):
            await self.client().fetch('ABC123')
        self.assertEqual(self.commands[-1], 5195)
        self.wrong_room = False
        self.ended = True
        with self.assertRaisesRegex(self.p.QueryError, '进行|结束'):
            await self.client().fetch('ABC123')
        self.assertEqual(self.commands[-1], 5195)

    async def test_observer_limit_and_cleanup_failure_never_succeed(self):
        self.errors[5191] = 11082
        with self.assertRaisesRegex(self.p.QueryError, '观战|11082'):
            await self.client().fetch('ABC123')
        self.assertNotIn(5193, self.commands)
        self.errors = {5195: 11001}
        with self.assertRaises(self.p.QueryError):
            await self.client().fetch('ABC123')

    async def test_timeout_and_cancellation_attempt_exit(self):
        self.delay_refresh = True
        with self.assertRaisesRegex(self.p.QueryError, '超时'):
            await self.client().fetch('ABC123')
        self.assertEqual(self.commands[-1], 5195)
        self.refresh_seen.clear()
        task = asyncio.create_task(self.client().fetch('ABC123'))
        await asyncio.wait_for(self.refresh_seen.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.commands[-1], 5195)


class HandRenderingTests(unittest.TestCase):
    def test_title_header_assets_and_duplicate_badge(self):
        rendering = importlib.import_module(f'{PACKAGE}.rendering')
        cards = importlib.import_module(f'{PACKAGE}.card_rendering')
        snapshot = {'map_type': 4, 'round': 1, 'captured_at': 1700000000, 'watch_code': 'ABC1234',
                    'players': [{'slot': 0, 'name': '玩家', 'hero_id': 101,
                                 'cards': [{'id': 10001}, {'id': 10001}]}]}
        texts = []
        original = rendering._text
        def capture(canvas, value, *args, **kwargs):
            texts.append(value)
            return original(canvas, value, *args, **kwargs)
        with patch.object(rendering, '_text', side_effect=capture), \
             patch.object(cards, 'render_card', wraps=cards.render_card) as card, \
             patch.object(rendering, '_image', wraps=rendering._image) as assets:
            payload = rendering.render_hands(snapshot)
        self.assertIn('玩家手牌预览 · 观战码 ABC1234', texts)
        self.assertIn('手牌 2 张', texts)
        self.assertEqual(card.call_count, 1)
        paths = [call.args[0] for call in assets.call_args_list]
        self.assertIn('settlement/BattleSettlement/qees2g.png', paths)
        self.assertIn(rendering.PORTRAITS['101'], paths)
        image = Image.open(io.BytesIO(payload)).convert('RGB')
        pixels = list(image.crop((263, 485, 286, 535)).getdata())
        self.assertTrue(any(r > 240 and g > 240 and b > 240 for r, g, b in pixels))
        self.assertTrue(any(r < 10 and g < 10 and b < 10 for r, g, b in pixels))

    def test_cards_have_no_extra_labels_below_the_native_face(self):
        rendering = importlib.import_module(f'{PACKAGE}.rendering')
        snapshot = {'map_type': 4, 'round': 1, 'captured_at': 1700000000,
            'players': [{'slot': 0, 'name': '玩家', 'hero_id': 101,
                         'cards': [{'id': 10001}]}]}
        texts = []
        def capture(canvas, value, *args, **kwargs):
            texts.append(str(value))
        with patch.object(rendering, '_text', side_effect=capture):
            rendering.render_hands(snapshot)
        self.assertFalse(any(value.startswith('1. ') for value in texts))

    def test_oversized_image_is_rejected_before_allocating_canvas(self):
        rendering = importlib.import_module(f'{PACKAGE}.rendering')
        error = importlib.import_module(f'{PACKAGE}.protocol').QueryError
        data = {'players': [{'cards': [{'id': None}] * 128} for _ in range(4)]}
        with patch.object(rendering, '_sprite') as background:
            with self.assertRaisesRegex(error, '图片|数量'):
                rendering.render_hands(data)
        background.assert_not_called()

    def test_hidden_known_and_unknown_cards_render_without_omissions(self):
        rendering = importlib.import_module(f'{PACKAGE}.rendering')
        self.assertTrue(hasattr(rendering, 'render_hands'), '手牌图片尚未实现')
        names = json.loads((ROOT / 'plugins/airi_astral_party/assets/cards.json').read_text(encoding='utf-8'))
        self.assertTrue(names.get('21001', {}).get('name'))
        snapshot = {'room_id': '100', 'map_type': 4, 'round': 8, 'captured_at': 1700000000,
            'players': [{'uid': str(i + 1), 'slot': i, 'name': f'测试玩家{i}', 'hero_id': 101,
                         'cards': [{'id': None}, {'id': 21001}, {'id': 999999}]} for i in range(4)]}
        texts = []
        calls = []
        original = rendering._text
        def capture(canvas, text, *args, **kwargs):
            texts.append(str(text))
            return original(canvas, text, *args, **kwargs)
        cards = importlib.import_module(f'{PACKAGE}.card_rendering')
        original_card = cards.render_card
        def capture_card(card, player, mode):
            calls.append((player['slot'], card['id']))
            return original_card(card, player, mode)
        with patch.object(rendering, '_text', side_effect=capture), patch.object(cards, 'render_card', side_effect=capture_card):
            picture = Image.open(io.BytesIO(rendering.render_hands(snapshot)))
            picture.load()
        self.assertEqual(picture.format, 'PNG')
        self.assertTrue(any('不可见' in text for text in texts))
        self.assertTrue(any('未收录' in text for text in texts))
        self.assertEqual(calls, [(slot, card) for slot in range(4) for card in (None, 21001, 999999)])
        self.assertFalse(any(names['21001']['name'] in text for text in texts))
        for slot in range(4):
            self.assertTrue(any(f'测试玩家{slot}' in text for text in texts))
