import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, fields, replace
from pathlib import Path

import psutil
from filelock import FileLock, Timeout

from .protocol import QueryError
from .settings import CLIENT_VERSION, Settings, load_settings


MAX_LOG_BYTES = 16 * 1024 * 1024
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / 'data/astral_party/config.json'
LOGIN_FIELDS = ('game_id', 'channel_id', 'app_id', 'sid', 'extra', 'device_id')


class ArgumentParser(argparse.ArgumentParser):
    def format_usage(self):
        return super().format_usage().replace('usage: ', '用法：')

    def format_help(self):
        return super().format_help().replace('usage: ', '用法：').replace('options:', '选项：')

    def error(self, message):
        self.exit(2, '参数格式不正确，请使用 --help 查看用法。\n')


def parse_login_log(text):
    values = {}
    records = text.splitlines()
    latest_login = max((index for index, line in enumerate(records)
                        if line.lstrip('\ufeff').startswith('SDK登录成功: sid=')), default=-1)
    lines = iter(enumerate(records))
    for index, raw in lines:
        line = raw.lstrip('\ufeff')
        if line.startswith(('[BnSdkInit] SDK初始化成功', '[BnSdkInit] SDK初始化失败')):
            values.clear()
        elif line.startswith('[BnSdkInit] 设备ID为：'):
            values['device_id'] = line.split('：', 1)[1].strip()
        elif line.startswith('[BnSdkInit] 获取SDK参数成功: gameID='):
            match = re.fullmatch(r'\[BnSdkInit\] 获取SDK参数成功: gameID=(.*?), channelID=(.*?), appID=(.*)', line)
            if not match:
                raise QueryError('游戏日志中的 SDK 参数不完整，请重新启动游戏并登录专用账号')
            values.update(zip(('game_id', 'channel_id', 'app_id'), (part.strip() for part in match.groups())))
        elif line.startswith(('SDK注销账号', '[BnSdkManager] 已清除旧的登录信息',
                              '[BnSdkManager] 已清除Sid', '[BnSdkManager] SDK登录失败',
                              '[BnSdkManager] SDK登录取消', '[BnSdkManager] 已清除登录信息',
                              '[BnSdkManager] 异常处理：已清除登录信息',
                              '[BnSdkManager] ========== 开始调用SDK登录接口')):
            values.pop('sid', None)
            values.pop('extra', None)
        elif line.startswith('SDK登录成功: sid='):
            if index != latest_login:
                continue
            content = line.removeprefix('SDK登录成功: sid=')
            if ', extra=' not in content:
                raise QueryError('游戏日志中的登录结果不完整，请重新登录专用账号')
            sid, extra = content.split(', extra=', 1)
            if extra.startswith(('{', '[')):
                while True:
                    if len(extra) > 8192:
                        raise QueryError('SDK 附加参数过长，无法保存配置')
                    try:
                        json.loads(extra)
                        break
                    except ValueError:
                        following_record = next(lines, None)
                        following = following_record[1] if following_record is not None else None
                        if following is None or not following.strip() or following.startswith(('UnityEngine.', '(Filename:', '[BnSdk', 'SDK')):
                            raise QueryError('SDK 附加参数不完整，请在登录结束后重试') from None
                        extra += '\n' + following
            values.update(sid=sid.strip(), extra=extra)
    if any(not values.get(key) or values[key].lower() in ('null', '空', '(null)')
           for key in LOGIN_FIELDS if key != 'extra') or 'extra' not in values:
        raise QueryError('未找到完整有效的本次 SDK 登录结果，请用专用账号登录并保持游戏大厅打开')
    result = Settings(**values)
    replace(result, host='127.0.0.1').validate()
    return result


def read_login_log(path):
    try:
        with Path(path).open('rb') as handle:
            size = os.fstat(handle.fileno()).st_size
            offset = max(0, size - MAX_LOG_BYTES)
            handle.seek(offset)
            data = handle.read(min(size, MAX_LOG_BYTES))
        if offset:
            data = data.partition(b'\n')[2]
        if data and not data.endswith(b'\n'):
            raise QueryError('游戏日志尚有未完成的写入，请稍等片刻再运行工具')
        return parse_login_log(data.decode('utf-8-sig'))
    except (OSError, UnicodeError):
        raise QueryError('无法读取 UTF-8 游戏日志，请检查 --log-file 指定的 Player.log 文件') from None


def detect_endpoint(port, pid=None):
    endpoints = set()
    try:
        for process in psutil.process_iter(['pid', 'name']):
            if process.info['name'] != '吉星派对.exe' or (pid is not None and process.info['pid'] != pid):
                continue
            try:
                for connection in process.net_connections(kind='tcp'):
                    if connection.status == psutil.CONN_ESTABLISHED and connection.raddr and connection.raddr[1] == port:
                        endpoints.add((connection.raddr[0], connection.raddr[1]))
            except (psutil.Error, OSError):
                continue
    except (psutil.Error, OSError):
        raise QueryError('无法读取游戏连接，请使用 --host 手动指定服务器地址') from None
    if len(endpoints) != 1:
        raise QueryError('无法唯一确定游戏服务器，请保持专用账号的游戏大厅打开，或使用 --host 指定服务器地址')
    return next(iter(endpoints))


def protect_file(path):
    try:
        if os.name == 'nt':
            result = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True,
                                    text=True, check=True, timeout=10)
            sid = next(csv.reader(result.stdout.strip().splitlines()))[-1]
            if not re.fullmatch(r'S-\d+(?:-\d+)+', sid):
                raise ValueError
            subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                            f'*{sid}:(F)', '*S-1-5-18:(F)'], capture_output=True, check=True, timeout=10)
        else:
            os.chmod(path, 0o600)
    except (OSError, ValueError, StopIteration, subprocess.SubprocessError):
        raise QueryError('无法限制配置文件访问权限，已停止保存；请检查当前用户的目录权限') from None


def sync_directory(path):
    if sys.platform == 'win32':
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_settings(path, settings):
    path = Path(path)
    settings.validate(require_session=False)
    encoded = json.dumps(asdict(settings), ensure_ascii=False, indent=2).encode('utf-8')
    if len(encoded) > 65536:
        raise QueryError('账号配置超过大小限制，原文件未变更')
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
        protect_file(temporary)
        with temporary.open('wb') as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    except OSError:
        raise QueryError('账号配置保存失败，请检查目录权限；停止后续授权操作') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_config(path, capture, host, port, client_version):
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with FileLock(str(path) + '.lock', timeout=3):
            existing = {}
            if path.exists():
                try:
                    if path.stat().st_size > 65536:
                        raise ValueError
                    existing = json.loads(path.read_text(encoding='utf-8-sig'))
                    if not isinstance(existing, dict) or set(existing) - {item.name for item in fields(Settings)}:
                        raise ValueError
                except (OSError, ValueError, TypeError):
                    raise QueryError('现有账号配置损坏或不可读，原文件已保留，请检查后重试') from None
            values = asdict(Settings()) | existing
            values.update({key: getattr(capture, key) for key in LOGIN_FIELDS})
            values.update(host=host, port=port, client_version=client_version)
            values['renewal'] = {}
            settings = Settings(**values)
            write_settings(path, settings)
    except (OSError, Timeout):
        raise QueryError('账号配置保存失败，原文件未变更，请检查目录权限或稍后重试') from None


def main(argv=None):
    parser = ArgumentParser(description='吉星派对飞魔专用账号配置、登录与会话更新工具', add_help=False)
    parser.add_argument('-h', '--help', action='help', help='显示帮助并退出')
    parser.add_argument('--log-file', type=Path,
                        default=Path.home() / 'AppData/LocalLow/feimo/吉星派对/Player.log', help='本次登录的游戏日志路径')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='插件配置输出路径')
    parser.add_argument('--host', help='手动指定游戏 TCP 服务器地址；留空则读取游戏进程连接')
    parser.add_argument('--port', type=int, default=8800, help='游戏 TCP 端口，默认 8800')
    parser.add_argument('--pid', type=int, help='仅检查指定的吉星派对游戏进程')
    parser.add_argument('--client-version', default=CLIENT_VERSION, help='游戏登录版本，默认 3.2.0，来自资源配置表')
    parser.add_argument('--yes', action='store_true', help='已完成专用账号登录，直接读取并确认写入或更新配置')
    parser.add_argument('--dry-run', action='store_true', help='只显示脱敏检查结果，不写入配置')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--login', action='store_true', help='私密输入飞魔手机号和密码，生成可迁移到 Linux 的自动登录配置')
    mode.add_argument('--refresh', action='store_true', help='使用已有授权联网续期；适用于 Linux 定时任务')
    mode.add_argument('--check', action='store_true', help='离线检查已有配置及续期状态，不读取游戏日志')
    parser.add_argument('--sdk-channel', default='test_junhai', help='飞魔 SDK 安装渠道标识；无 SetupInfo.ini 时沿用客户端默认值')
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.port <= 65535 or (args.pid is not None and args.pid <= 0):
            raise QueryError('端口或进程编号无效')
        print('吉星派对 · 专用查询账号配置工具')
        if args.login or args.refresh or args.check:
            from .renewal import authorization_status, login, refresh
            if args.dry_run and not args.check:
                raise QueryError('联网授权与续期不支持 --dry-run；请使用 --check 离线检查')
            if args.check:
                settings = load_settings(args.output)
                settings.validate(require_session=False)
                print(authorization_status(settings))
                print('仅检查本地配置，未验证服务器是否接受授权。')
            elif args.login:
                login(args.output, sdk_channel=args.sdk_channel)
                print('飞魔自动登录凭据与 SDK 会话已保存，可迁移到 Linux；请再验证实际玩家查询。')
            else:
                changed = refresh(args.output)
                print('飞魔 SDK 会话已更新。' if changed else '尚未到续期间隔，本次未联网。')
            return 0
        if not args.yes:
            print('请在官方客户端使用自行注册的专用账号登录，并保持游戏大厅打开。')
            print('工具将读取所选游戏日志中的最新 SDK 登录结果，并生成本机查询配置。')
            input('完成后按回车继续，按 Ctrl+C 取消：')
        capture = read_login_log(args.log_file)
        host, port = (args.host, args.port) if args.host else detect_endpoint(args.port, args.pid)
        replace(capture, host=host, port=port, client_version=args.client_version).validate()
        print(f'服务器：{host}:{port}；应用版本：{args.client_version}')
        print('游戏、渠道、应用标识：已提取')
        print('SDK 会话与设备标识：已提取，内容不显示')
        print(f'配置位置：{args.output.resolve()}')
        if args.dry_run:
            print('检查完成，未写入配置；此检查不连接游戏服务器。')
            return 0
        if not args.yes and input('写入配置（已有配置的账号参数将更新）？[y/N]：').strip().lower() != 'y':
            print('已取消，配置未变更。')
            return 0
        save_config(args.output, capture, host, port, args.client_version)
        print('配置已安全保存。请正常关闭游戏，再向 Airi 发送 astral status 和 astral UID 验证查询。')
        print('当前只保存临时会话。Linux 长期运行前，请再执行本工具 --login 配置飞魔专用账号。')
        return 0
    except QueryError as error:
        print(f'操作未完成：{error}')
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\n已取消，未继续保存配置。')
        return 1
    except Exception as error:
        print(f'工具运行失败（{type(error).__name__}），请检查本机环境；未输出登录参数。')
        return 1
