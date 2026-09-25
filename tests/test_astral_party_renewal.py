import importlib
import io
import http.client
import json
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.parse
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_astral_party_renewal_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'plugins/airi_astral_party')]
sys.modules[PACKAGE] = package


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.settings = importlib.import_module(f'{PACKAGE}.settings')
        self.setup = importlib.import_module(f'{PACKAGE}.account_setup')
        self.renewal = importlib.import_module(f'{PACKAGE}.renewal')
        self.auth = {'provider': 'feimo', 'phone': '13800000000', 'password_digest': 'a' * 32,
                     'sdk_channel': 'test_junhai', 'device_name': 'dev', 'os_version': 'Windows',
                     'user_id': 'account-id', 'session_at': 1}
        self.capture = self.settings.Settings(host='127.0.0.1', game_id='g', channel_id='c',
                                             app_id='110001950', sid='old-session', extra='bn',
                                             device_id='sdk-device', renewal=self.auth)
        self.reply = {'ret': 1, 'content': {'authorize_code': 'new-session', 'user_id': 'account-id'}}

    def test_feimo_password_and_sign_vectors(self):
        import hashlib
        expected = hashlib.md5(b'secret5ebe2294ecd0e0f08eab7690d2a6ee69').hexdigest()
        self.assertEqual(self.renewal.password_digest('secret'), expected)
        for app, key in [('110001950', '67f6128727f2d8345a30d2d041797571'),
                         ('110001958', '6586f8d6ab34f805997a06732fa181df')]:
            self.assertEqual(self.renewal.sdk_sign({'z': '2', 'a': '1'}, app),
                             hashlib.md5(('a=1z=2' + key).encode()).hexdigest())
        with self.assertRaises(ValueError):
            self.renewal.sdk_sign({}, 'unknown')

    def test_refresh_uses_feimo_only_and_reuses_root_credential_after_restart(self):
        calls = []
        def transport(method, url, data=None):
            calls.append(url)
            self.assertEqual((method, url), ('POST', self.renewal.AUTHORIZE_URL))
            self.assertEqual(data['login_type'], '19')
            self.assertEqual(data['tel_num'], '13800000000')
            self.assertEqual(data['password'], 'a' * 32)
            self.assertEqual(data['device_id'], 'sdk-device')
            self.assertNotIn('channel_sid', data)
            self.assertNotIn('userId', data)
            return self.reply
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            self.setup.write_settings(path, self.capture)
            with patch.object(self.renewal, 'request_json', side_effect=transport):
                self.assertTrue(self.renewal.refresh(path, now=100000))
                self.assertFalse(self.renewal.refresh(path, now=100001))
                self.assertTrue(self.renewal.refresh(path, now=200000))
            saved = self.settings.load_settings(path)
            self.assertEqual(saved.sid, 'new-session')
            self.assertEqual(saved.renewal['password_digest'], 'a' * 32)
            self.assertEqual(len(calls), 2)
            self.assertNotIn('13800000000', repr(saved))

    def test_login_prompts_privately_and_persists_only_after_valid_response(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            self.setup.write_settings(path, replace(self.capture, renewal={}))
            reply = dict(self.reply, content=json.dumps(self.reply['content']))
            with patch.object(self.renewal.getpass, 'getpass', side_effect=['13800000000', 'private-password']), patch.object(self.renewal, 'request_json', return_value=reply), patch('builtins.print') as output:
                self.renewal.login(path)
            self.assertNotIn('private-password', path.read_text(encoding='utf-8'))
            self.assertEqual(self.settings.load_settings(path).renewal['provider'], 'feimo')
            self.assertNotIn('13800000000', str(output.call_args_list))

    def test_denial_mismatch_and_missing_fields_preserve_old_config(self):
        for reply in ({'ret': 0, 'message': 'private'},
                      {'ret': 1, 'content': {'authorize_code': 'new', 'user_id': 'different'}},
                      {'ret': 1, 'content': {'authorize_code': 'new'}},
                      {'ret': True, 'content': self.reply['content']}):
            with self.subTest(reply=reply), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'config.json'
                self.setup.write_settings(path, self.capture)
                previous = path.read_bytes()
                with patch.object(self.renewal, 'request_json', return_value=reply), self.assertRaises(ValueError) as caught:
                    self.renewal.refresh(path, now=100000)
                self.assertEqual(path.read_bytes(), previous)
                self.assertNotIn('private', str(caught.exception))

    def test_write_failure_keeps_reusable_credential_and_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            self.setup.write_settings(path, self.capture)
            with patch.object(self.renewal, 'request_json', return_value=self.reply):
                with patch.object(self.setup.os, 'replace', side_effect=OSError), self.assertRaises(ValueError):
                    self.renewal.refresh(path, now=100000)
                self.assertEqual(self.settings.load_settings(path).renewal, self.auth)
                self.assertTrue(self.renewal.refresh(path, now=100001))

    def test_reexport_clears_previous_renewal_and_preserves_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            self.setup.write_settings(path, replace(self.capture, cooldown=30))
            self.setup.save_config(path, self.capture, self.capture.host, 8800, '3.2.1')
            saved = self.settings.load_settings(path)
            self.assertEqual(saved.renewal, {})
            self.assertEqual(saved.cooldown, 30)

    def test_offline_check_and_legacy_config_never_attempt_login(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            self.setup.write_settings(path, replace(self.capture, renewal={}))
            with patch.object(self.renewal, 'request_json', side_effect=AssertionError('不能联网')), patch('builtins.print'):
                self.assertEqual(self.setup.main(['--check', '--output', str(path)]), 0)
                self.assertEqual(self.setup.main(['--refresh', '--output', str(path)]), 1)
                self.assertEqual(self.setup.main(['--login', '--dry-run', '--output', str(path)]), 1)

    def test_bad_authorization_rejected_without_exposing_material(self):
        for auth in (None, {'token': 'private'}, dict(self.auth, provider='other'),
                     dict(self.auth, password_digest='private'), dict(self.auth, phone='private'),
                     dict(self.auth, session_at=float('nan'))):
            with self.subTest(kind=type(auth).__name__), self.assertRaises(ValueError) as caught:
                self.renewal.validate_authorization(auth)
            self.assertNotIn('private', str(caught.exception))

    def test_http_encoding_redirects_and_safe_network_errors(self):
        class Opener:
            def open(inner, request, timeout):
                self.assertEqual(timeout, 15)
                self.assertEqual(urllib.parse.parse_qs(request.data.decode()), {'password': ['a+b=&private']})
                return io.BytesIO(b'{"ret":0}')
        with patch.object(self.renewal.urllib.request, 'build_opener', return_value=Opener()):
            self.assertEqual(self.renewal.request_json('POST', self.renewal.AUTHORIZE_URL, {'password': 'a+b=&private'}), {'ret': 0})
        with self.assertRaises(ValueError):
            self.renewal.request_json('POST', 'https://example.com', {})
        with self.assertRaisesRegex(ValueError, '重定向'):
            self.renewal.NoRedirect().redirect_request(None, None, 307, '', {}, 'https://example.com')
        for failure in (urllib.error.URLError('private'), http.client.IncompleteRead(b'private')):
            opener = types.SimpleNamespace(open=lambda *a, **k: None)
            with patch.object(opener, 'open', side_effect=failure), patch.object(self.renewal.urllib.request, 'build_opener', return_value=opener), self.assertRaises(ValueError) as caught:
                self.renewal.request_json('POST', self.renewal.AUTHORIZE_URL, {})
            self.assertNotIn('private', str(caught.exception))

    def test_linux_directory_sync_closes_on_failure(self):
        with patch.object(self.setup.sys, 'platform', 'linux'), patch.object(self.setup.os, 'open', return_value=42), patch.object(self.setup.os, 'fsync', side_effect=OSError), patch.object(self.setup.os, 'close') as close:
            with self.assertRaises(OSError):
                self.setup.sync_directory(Path('config-parent'))
            close.assert_called_once_with(42)

    def test_hidden_input_unavailable_never_calls_network_or_changes_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            self.setup.write_settings(path, self.capture)
            previous = path.read_bytes()
            with patch.object(self.renewal.getpass, 'getpass', side_effect=self.renewal.getpass.GetPassWarning), patch.object(self.renewal, 'request_json') as request, patch('builtins.print'):
                with self.assertRaisesRegex(ValueError, '隐藏输入'):
                    self.renewal.login(path)
            request.assert_not_called()
            self.assertEqual(path.read_bytes(), previous)

    def test_concurrent_refresh_stops_before_authorization(self):
        from filelock import FileLock
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            self.setup.write_settings(path, self.capture)
            previous = path.read_bytes()
            with FileLock(str(path) + '.lock'), patch.object(self.renewal, 'request_json') as request:
                with self.assertRaisesRegex(ValueError, '其他进程'):
                    self.renewal.refresh(path, now=100000)
            request.assert_not_called()
            self.assertEqual(path.read_bytes(), previous)

    def test_http_error_and_oversized_response_are_rejected_without_content(self):
        body = io.BytesIO(b'private')
        failure = urllib.error.HTTPError(self.renewal.AUTHORIZE_URL, 401, 'private', {}, body)
        opener = types.SimpleNamespace(open=lambda *a, **k: None)
        with patch.object(opener, 'open', side_effect=failure), patch.object(self.renewal.urllib.request, 'build_opener', return_value=opener), self.assertRaises(ValueError) as caught:
            self.renewal.request_json('POST', self.renewal.AUTHORIZE_URL, {})
        self.assertTrue(body.closed)
        self.assertNotIn('private', str(caught.exception))
        with patch.object(opener, 'open', return_value=io.BytesIO(b'x' * 65537)), patch.object(self.renewal.urllib.request, 'build_opener', return_value=opener), self.assertRaisesRegex(ValueError, '超过限制'):
            self.renewal.request_json('POST', self.renewal.AUTHORIZE_URL, {})


if __name__ == '__main__':
    unittest.main()
