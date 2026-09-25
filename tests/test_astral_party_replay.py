import copy
import http.client
import importlib
import struct
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


PACKAGE = '_astral_replay_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'plugins/airi_astral_party')]
sys.modules[PACKAGE] = package
replay = importlib.import_module(PACKAGE + '.replay')
protocol = importlib.import_module(PACKAGE + '.protocol')


def fixture():
    snapshot = {
        'show': {'isShowFight': True},
        'selected': {'replayId': '123456', 'version': '3.2.0-2.0.0', 'time': '500', 'mapType': 4},
        'details': [{'playerId': '123', 'heroId': 306, 'slot': 0, 'background': 71001}],
    }
    room = {'id': 456, 'mapType': 4, 'map_id': 82016, 'round': 11, 'difficulty': 3,
            'players': [{'id': 123, 'slot': 0, 'nick': '测试玩家', 'level': 23,
                         'hero': {'hero_id': 306, 'standingPainting': 100306001, 'teamId': 10,
                                  'select_relics': {50013: True, 50016: False}},
                         'fashionPlan': [{'plan': 1, 'fashion': {1: 70001, 2: 71010}}]}]}
    finish = {'room_id': 456, 'winer': 10, 'finish_time': 500, 'replayId': '123456',
              'version': '3.2.0-2.0.0', 'mapType': 4,
              'newAchieve': {123: {'killCount': 11, 'totalDamage': 261, 'totalGold': 166}}}
    return snapshot, room, finish


def frame(command, name, **values):
    payload = protocol.message(name, **values).SerializeToString()
    return struct.pack('>hi', command, len(payload)) + payload


def recording(room, finish):
    return frame(1113, 'ReplaySnapshotS2C', room=room) * 2 + frame(1016, 'GameFinishS2C', **finish)


class ReplayTests(unittest.TestCase):
    def test_normalizes_only_display_fields_and_preserves_zero(self):
        snapshot, room, finish = fixture()
        original = copy.deepcopy(snapshot)
        result = replay.parse_replay(recording(room, finish), snapshot)
        player = result['players']['123']
        self.assertEqual(player['stats']['totalDamage'], 261)
        self.assertEqual(player['stats']['treatmentScore'], 0)
        self.assertEqual(player['relics'], [50013])
        self.assertEqual(player['background'], 71010)
        self.assertTrue(player['winner'])
        self.assertEqual(result['round'], 11)
        self.assertNotIn('token', player)
        self.assertEqual(snapshot, original)

    def test_terminal_snapshot_is_discarded_like_game_settlement_loader(self):
        snapshot, room, finish = fixture()
        old = copy.deepcopy(room)
        old['round'] = 3
        data = frame(1113, 'ReplaySnapshotS2C', room=old) + frame(1113, 'ReplaySnapshotS2C', room=room) + frame(1016, 'GameFinishS2C', **finish)
        self.assertEqual(replay.parse_replay(data, snapshot)['round'], 3)

    def test_rejects_mismatched_record_and_players(self):
        for field, value in [('replayId', '9'), ('version', 'old'), ('finish_time', 8), ('mapType', 1), ('room_id', 1)]:
            with self.subTest(field=field):
                snapshot, room, finish = fixture()
                finish[field] = value
                with self.assertRaises(replay.QueryError):
                    replay.parse_replay(recording(room, finish), snapshot)
        for field, value in [('id', 124), ('slot', 1), ('hero_id', 101)]:
            with self.subTest(field=field):
                snapshot, room, finish = fixture()
                target = room['players'][0]['hero'] if field == 'hero_id' else room['players'][0]
                target[field] = value
                with self.assertRaises(replay.QueryError):
                    replay.parse_replay(recording(room, finish), snapshot)

    def test_rejects_bad_framing_and_protobuf(self):
        snapshot, room, finish = fixture()
        valid = recording(room, finish)
        for data in [b'', valid[:-1], b'abc', struct.pack('>hi', 1113, -1),
                     struct.pack('>hi', 1113, replay.MAX_PAYLOAD + 1),
                     struct.pack('>hi', 1113, 1) + b'\xff' + frame(1016, 'GameFinishS2C', **finish)]:
            with self.subTest(size=len(data)), self.assertRaises(replay.QueryError):
                replay.parse_replay(data, snapshot)

    def test_missing_turn_snapshot_does_not_use_initial_room_as_final(self):
        snapshot, room, finish = fixture()
        data = frame(1003, 'RunningGameS2C', room=room) + frame(1016, 'GameFinishS2C', **finish)
        with self.assertRaises(replay.QueryError):
            replay.parse_replay(data, snapshot)

    def test_pvp_uses_settlement_gold_and_native_dense_ranks(self):
        snapshot, room, finish = fixture()
        snapshot['selected']['mapType'] = room['mapType'] = finish['mapType'] = 1
        room['players'][0]['hero'].update(lv=2, gold=25)
        finish['newAchieve'][123]['pvpResultGold'] = 30
        for uid, level, gold in ((124, 3, 5), (125, 2, 25)):
            player = copy.deepcopy(room['players'][0])
            player.update(id=uid, slot=uid - 123)
            player['hero'].update(lv=level, gold=gold)
            room['players'].append(player)
            snapshot['details'].append({'playerId': str(uid), 'heroId': 306, 'slot': uid - 123})
            finish['newAchieve'][uid] = {'pvpResultGold': gold}
        result = replay.parse_replay(recording(room, finish), snapshot)['players']
        self.assertEqual([result[str(uid)]['rank'] for uid in (123, 124, 125)], [2, 1, 2])
        self.assertEqual(result['123']['gold'], 30)
        self.assertEqual(result['123']['lv'], 2)

    def test_privacy_and_absent_replay_skip_download(self):
        for change in ('private', 'no_id', 'no_details'):
            snapshot, _, _ = fixture()
            if change == 'private':
                snapshot['show']['isShowFight'] = False
            elif change == 'no_id':
                snapshot['selected'].pop('replayId')
            else:
                snapshot['details'] = []
            with patch.object(replay, 'download') as download:
                self.assertIs(replay.enrich_snapshot(snapshot), snapshot)
                download.assert_not_called()

    def test_download_errors_preserve_basic_details(self):
        for error in [OSError(), http.client.IncompleteRead(b'a'), http.client.BadStatusLine('bad'), ValueError()]:
            snapshot, _, _ = fixture()
            with patch.object(replay, 'download', side_effect=error):
                result = replay.enrich_snapshot(snapshot)
            self.assertTrue(result['settlementUnavailable'])
            self.assertEqual(result['details'], snapshot['details'])
            self.assertNotIn('settlementUnavailable', snapshot)

    def test_fixed_origin_streaming_limit_and_no_credentials(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read1.side_effect = [b'a', b'b', b'']
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(replay.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(replay.download('123456'), b'ab')
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://sereplaycn.feimogames.com/prod/123456')
        self.assertEqual(request.header_items(), [])
        response.read.assert_not_called()
        with patch.object(replay.urllib.request, 'build_opener', return_value=opener), self.assertRaises(replay.QueryError):
            replay.download('../other')
        response.read1.side_effect = [b'a']
        with patch.object(replay.urllib.request, 'build_opener', return_value=opener), patch.object(replay.time, 'monotonic', side_effect=[0, 18]):
            with self.assertRaises(replay.QueryError):
                replay.download('123456')


if __name__ == '__main__':
    unittest.main()
