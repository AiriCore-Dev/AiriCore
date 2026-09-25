import asyncio
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_astral_party_admin_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'plugins/airi_astral_party')]
sys.modules[PACKAGE] = package


class AccountAdminTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertTrue((ROOT / 'plugins/airi_astral_party/account_admin.py').exists(), '缺少 Bot 账号管理入口')
        self.admin = importlib.import_module(PACKAGE + '.account_admin')
        self.bootstrap = importlib.import_module(PACKAGE + '.bootstrap')
        self.renewal = importlib.import_module(PACKAGE + '.renewal')
        self.settings = importlib.import_module(PACKAGE + '.settings')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'config.json'
        self.manager = self.admin.AccountAdmin(self.path, asyncio.Lock(), asyncio.to_thread)
        self.server = {'version': '3.2.1', 'route': '110001958',
                       'noticeUrl': '', 'serverUrl': 'se-jump-cn-01.feimogames.com:8800'}
        self.reply = {'ret': 1, 'content': {'authorize_code': 'private-sid', 'user_id': 'opaque-id'}}

    async def test_first_login_without_config_or_client_then_clear_and_login_again(self):
        credentials = self.admin.Credentials('13800000000', 'a' * 32)
        with patch.object(self.bootstrap, 'request_server', return_value=self.server), patch.object(self.renewal, 'request_json', return_value=self.reply):
            view = await self.manager.handle('login', True, True, credentials)
            self.assertEqual(view['kind'], 'notice')
            self.assertNotIn('private-sid', str(view))
            saved = self.settings.load_settings(self.path)
            self.assertEqual(saved.host, 'se-jump-cn-01.feimogames.com')
            self.assertEqual((saved.game_id, saved.channel_id, saved.app_id), ('120000182', '2', '110001958'))
            self.assertEqual(saved.sid, 'private-sid')
            device = saved.device_id
            await self.manager.handle('clear confirm', True, True)
            cleared = self.settings.load_settings(self.path)
            self.assertEqual((cleared.sid, cleared.renewal), ('', {}))
            self.assertNotIn('13800000000', self.path.read_text(encoding='utf-8'))
            with self.assertRaises(ValueError):
                cleared.validate()
            await self.manager.handle('login', True, True, credentials)
            self.assertEqual(self.settings.load_settings(self.path).device_id, device)

    async def test_permission_rejection_has_no_file_or_network_effect(self):
        def forbidden(*args, **kwargs):
            self.fail('未授权操作不得访问网络')
        with patch.object(self.bootstrap, 'request_server', side_effect=forbidden), patch.object(self.renewal, 'request_json', side_effect=forbidden):
            for private, verified in ((False, True), (True, False), (False, False)):
                for command in ('setup', 'login', 'refresh', 'clear confirm', 'check'):
                    with self.assertRaises(ValueError):
                        await self.manager.handle(command, private, verified, self.admin.Credentials('13800000000', 'a' * 32))
            self.assertFalse(self.path.exists())

    async def test_bootstrap_rejects_empty_wrong_version_or_untrusted_destination(self):
        for change in ({'serverUrl': ''}, {'route': 'wrong'}, {'version': '4.0'},
                       {'serverUrl': '127.0.0.1:8800'}, {'serverUrl': 'evil.com:8800'},
                       {'serverUrl': 'se-jump-cn-01.feimogames.com:22'}):
            with self.subTest(change=change), patch.object(self.bootstrap, 'request_server', return_value=self.server | change):
                with self.assertRaises(ValueError):
                    await self.manager.handle('setup', True, True)
                self.assertFalse(self.path.exists())

    async def test_failed_login_and_clear_without_confirmation_preserve_config(self):
        with patch.object(self.bootstrap, 'request_server', return_value=self.server):
            await self.manager.handle('setup', True, True)
        before = self.path.read_bytes()
        with patch.object(self.renewal, 'request_json', return_value={'ret': 0}):
            with self.assertRaises(ValueError):
                await self.manager.handle('login', True, True, self.admin.Credentials('13800000000', 'a' * 32))
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(ValueError):
            await self.manager.handle('clear', True, True)
        self.assertEqual(self.path.read_bytes(), before)

    async def test_forced_refresh_ignores_age_and_auto_tick_respects_interval(self):
        calls = []
        def transport(*args, **kwargs):
            calls.append(kwargs['data']['login_type'])
            return self.reply
        with patch.object(self.bootstrap, 'request_server', return_value=self.server), patch.object(self.renewal, 'request_json', side_effect=transport):
            await self.manager.handle('login', True, True, self.admin.Credentials('13800000000', 'a' * 32))
            self.assertFalse(await self.manager.maintain())
            await self.manager.handle('refresh', True, True)
            self.assertEqual(calls, ['19', '19'])
            current = self.settings.load_settings(self.path)
            with patch.object(self.renewal.time, 'time', return_value=current.renewal['session_at'] + 25000):
                self.assertTrue(await self.manager.maintain())
            await self.manager.handle('clear confirm', True, True)
            self.assertFalse(await self.manager.maintain())
            self.assertEqual(len(calls), 3)

    async def test_setup_preserves_logged_in_account_and_bad_config(self):
        with patch.object(self.bootstrap, 'request_server', return_value=self.server), patch.object(self.renewal, 'request_json', return_value=self.reply):
            await self.manager.handle('login', True, True, self.admin.Credentials('13800000000', 'a' * 32))
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                await self.manager.handle('setup 110001950', True, True)
            self.assertEqual(self.path.read_bytes(), before)
        self.path.write_text('{坏档', encoding='utf-8')
        with self.assertRaises(ValueError):
            await self.manager.handle('setup', True, True)
        self.assertEqual(self.path.read_text(encoding='utf-8'), '{坏档')

    async def test_public_server_request_uses_app_id_route_and_blocks_redirects(self):
        import io
        class Opener:
            def open(inner, request, timeout):
                self.assertEqual(request.full_url, 'https://se-web-cn.feimogames.com:7878/api/hotaddressServer/get?route=110001958&version=3.2.1')
                self.assertIsNone(request.data)
                return io.BytesIO(json.dumps(self.server).encode())
        with patch.object(self.bootstrap.urllib.request, 'build_opener', return_value=Opener()):
            self.assertEqual(self.bootstrap.discover('110001958'), ('se-jump-cn-01.feimogames.com', 8800))


if __name__ == '__main__':
    unittest.main()
