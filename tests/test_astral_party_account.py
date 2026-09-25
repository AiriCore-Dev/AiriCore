import importlib
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_astral_party_account_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'plugins/airi_astral_party')]
sys.modules[PACKAGE] = package


def login_log(sid='test-session-private', extra='{"user":"test-extra-private"}'):
    return '\n'.join((
        '[BnSdkInit] SDK初始化成功',
        '[BnSdkInit] 设备ID为：test-device-private',
        '[BnSdkInit] 获取SDK参数成功: gameID=game, channelID=channel, appID=app',
        '[BnSdkManager] 已清除旧的登录信息',
        f'SDK登录成功: sid={sid}, extra={extra}',
        '无关的游戏日志',
    )) + '\n'


class AccountToolTests(unittest.TestCase):
    def setUp(self):
        self.tool = importlib.import_module(f'{PACKAGE}.account_setup')

    def test_extract_original_log_format_without_echoing_credentials(self):
        capture = self.tool.parse_login_log(login_log())
        self.assertEqual(capture.sid, 'test-session-private')
        self.assertEqual(capture.extra, '{"user":"test-extra-private"}')
        self.assertEqual(capture.device_id, 'test-device-private')
        self.assertEqual((capture.game_id, capture.channel_id, capture.app_id), ('game', 'channel', 'app'))
        self.assertNotIn('private', repr(capture))

    def test_latest_session_and_login_invalidation(self):
        text = login_log('old-private') + '\n' + login_log('new-private')
        self.assertEqual(self.tool.parse_login_log(text).sid, 'new-private')
        for marker in ('[BnSdkManager] 已清除旧的登录信息', 'SDK注销账号',
                       '[BnSdkManager] SDK登录失败: ret=0', '[BnSdkInit] SDK初始化成功',
                       '[BnSdkInit] SDK初始化失败: ret=0', '[BnSdkManager] 异常处理：已清除登录信息'):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, '登录'):
                self.tool.parse_login_log(text + '\n' + marker)

    def test_incomplete_log_tail_never_falls_back_to_previous_account(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Player.log'
            for tail in ('SDK注销账号', '[BnSdkManager] ========== 开始调用SDK登录接口',
                         'SDK登录成功: sid=new', '日志正在写入'):
                path.write_text(login_log() + tail, encoding='utf-8')
                with self.subTest(tail=tail), self.assertRaisesRegex(ValueError, '写入'):
                    self.tool.read_login_log(path)
            path.write_text(login_log(), encoding='utf-8')
            self.assertEqual(self.tool.read_login_log(path).sid, 'test-session-private')

    def test_incomplete_oversized_or_missing_parameters_are_rejected(self):
        for text in (login_log().replace('test-device-private', ''),
                     login_log().replace('gameID=game', 'gameID='),
                     login_log(sid=''), login_log(sid='null'), login_log(sid='x' * 8193),
                     'SDK登录成功: sid=test-session-private, extra='):
            with self.subTest(length=len(text)), self.assertRaises(ValueError) as error:
                self.tool.parse_login_log(text)
            self.assertNotIn('test-session-private', str(error.exception))

    def test_extra_preserves_commas_and_multiline_json(self):
        for extra in ('', 'opaque, extra=value, more=1  ', '{\n  "a": "value,with=commas"\n}'):
            with self.subTest(extra=extra):
                self.assertEqual(self.tool.parse_login_log(login_log(extra=extra)).extra, extra)
        with self.assertRaises(ValueError):
            self.tool.parse_login_log(login_log(extra='{"broken":'))

    def test_new_login_recovers_from_older_broken_extra(self):
        old = login_log(sid='old-private', extra='{"broken":')
        for boundary in ('', '[BnSdkInit] SDK初始化成功\n'):
            with self.subTest(boundary=boundary):
                result = self.tool.parse_login_log(old + boundary + login_log(sid='new-private'))
                self.assertEqual(result.sid, 'new-private')
        with self.assertRaises(ValueError):
            self.tool.parse_login_log(login_log() + old)

    def test_endpoint_only_uses_game_connections_and_rejects_ambiguity(self):
        connection = lambda host, port: types.SimpleNamespace(status='ESTABLISHED', raddr=(host, port))
        game = Mock(info={'pid': 42, 'name': '吉星派对.exe'})
        game.net_connections.return_value = [connection('127.0.0.1', 8800), connection('127.0.0.1', 443)]
        other = Mock(info={'pid': 45, 'name': 'other.exe'})
        other.net_connections.return_value = [connection('192.0.2.1', 8800)]
        with patch.object(self.tool.psutil, 'process_iter', return_value=[game, other]):
            self.assertEqual(self.tool.detect_endpoint(8800), ('127.0.0.1', 8800))
            other.net_connections.assert_not_called()
            game.net_connections.return_value.append(connection('192.0.2.2', 8800))
            with self.assertRaisesRegex(ValueError, '--host'):
                self.tool.detect_endpoint(8800)

    def test_atomic_update_preserves_preferences_and_protects_bad_file(self):
        capture = self.tool.parse_login_log(login_log())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text('{"timeout":7,"cooldown":25}', encoding='utf-8')
            self.tool.save_config(path, capture, '127.0.0.1', 8800, '3.2.1')
            current = importlib.import_module(f'{PACKAGE}.settings').load_settings(path)
            self.assertEqual((current.timeout, current.cooldown), (7, 25))
            self.assertEqual(current.sid, 'test-session-private')
            original = path.read_bytes()
            with patch.object(self.tool.os, 'replace', side_effect=OSError('private-value')):
                with self.assertRaises(ValueError) as error:
                    self.tool.save_config(path, capture, '127.0.0.2', 8800, '3.2.1')
                self.assertNotIn('private-value', str(error.exception))
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(list(Path(directory).glob('*.tmp')))
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '原文件'):
                self.tool.save_config(path, capture, '127.0.0.1', 8800, '3.2.1')
            self.assertEqual(path.read_text(encoding='utf-8'), '{broken')

    def test_permissions_are_applied_before_secrets_are_written(self):
        capture = self.tool.parse_login_log(login_log())
        inspected = []

        def protect(path):
            inspected.append(Path(path).read_bytes())

        with tempfile.TemporaryDirectory() as directory, patch.object(self.tool, 'protect_file', side_effect=protect):
            self.tool.save_config(Path(directory) / 'config.json', capture, '127.0.0.1', 8800, '3.2.1')
        self.assertEqual(inspected, [b''])

    def test_permission_failure_preserves_original_and_leaves_no_secret_file(self):
        capture = self.tool.parse_login_log(login_log())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text('{}', encoding='utf-8')
            with patch.object(self.tool, 'protect_file', side_effect=self.tool.QueryError('权限设置失败')):
                with self.assertRaisesRegex(ValueError, '权限'):
                    self.tool.save_config(path, capture, '127.0.0.1', 8800, '3.2.1')
            self.assertEqual(path.read_text(encoding='utf-8'), '{}')
            self.assertFalse(list(Path(directory).glob('*.tmp')))

    def test_cli_failure_and_interactive_cancel_do_not_save(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, config = root / 'Player.log', root / 'config.json'
            log.write_text('SDK登录成功: sid=test-session-private, extra=', encoding='utf-8')
            arguments = ['--log-file', str(log), '--host', '127.0.0.1', '--output', str(config)]
            with patch('builtins.print') as output:
                self.assertEqual(self.tool.main(arguments + ['--yes']), 1)
                self.assertNotIn('test-session-private', str(output.call_args_list))
            log.write_text(login_log(), encoding='utf-8')
            with patch('builtins.input', side_effect=['', 'n']), patch('builtins.print'):
                self.assertEqual(self.tool.main(arguments), 0)
            self.assertFalse(config.exists())

    def test_cli_runs_without_nonebot_and_never_prints_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, config = root / 'Player.log', root / 'config.json'
            log.write_text(login_log(), encoding='utf-8')
            environment = os.environ.copy()
            environment['PYTHONIOENCODING'] = 'utf-8'
            command = [sys.executable, str(ROOT / 'plugins/airi_astral_party/account_tool.py'),
                       '--log-file', str(log), '--host', '127.0.0.1', '--output', str(config), '--yes']
            for options in (['--dry-run'], []):
                result = subprocess.run(command + options, cwd=root, env=environment,
                                        capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('private', result.stdout + result.stderr)
                if options:
                    self.assertFalse(config.exists())
            self.assertEqual(json.loads(config.read_text(encoding='utf-8'))['sid'], 'test-session-private')

    def test_cli_argument_errors_are_chinese_and_do_not_echo_values(self):
        parser = self.tool.ArgumentParser()
        with patch('sys.stderr') as stderr, self.assertRaises(SystemExit):
            parser.parse_args(['--invalid', 'test-session-private'])
        message = ''.join(str(call.args[0]) for call in stderr.write.call_args_list)
        self.assertIn('参数格式不正确', message)
        self.assertNotIn('test-session-private', message)
