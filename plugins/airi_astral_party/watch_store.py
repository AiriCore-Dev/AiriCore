import json
import os
import re
import tempfile
import threading
from pathlib import Path

from filelock import FileLock, Timeout

from .protocol import QueryError
from .whitelist import group_id


def watch_code(value):
    if not isinstance(value, str) or not re.fullmatch(r'[!-~]{1,64}', value):
        raise QueryError('观战码格式无效，请从游戏内复制：astral watch 观战码')
    return value


def room_id(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,19}', str(value)) or not 0 < int(value) < 2**63:
        raise QueryError('观战房间编号无效，请重新设置观战码')
    return str(int(value))


class GroupWatchStore:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _read(self):
        try:
            if not self.path.exists():
                return {}
            if self.path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError
            for group, target in data.items():
                if group_id(group) != group or not isinstance(target, dict) or set(target) != {'code', 'room_id'}:
                    raise ValueError
                watch_code(target['code'])
                if room_id(target['room_id']) != target['room_id']:
                    raise ValueError
            return data
        except (OSError, ValueError, TypeError):
            raise QueryError('吉星派对群观战记录损坏或不可读，请联系管理员；原文件已保留') from None

    def get(self, group):
        group = group_id(group)
        with self._lock:
            return self._read().get(group)

    def set(self, group, code, room):
        group = group_id(group)
        target = {'code': watch_code(code), 'room_id': room_id(room)}
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, FileLock(str(self.path) + '.lock', timeout=3):
                data = self._read()
                data[group] = target
                encoded = json.dumps(data, ensure_ascii=False, sort_keys=True).encode('utf-8')
                if len(encoded) > 2 * 1024 * 1024:
                    raise QueryError('群观战记录已达容量上限，请联系管理员')
                with tempfile.NamedTemporaryFile(dir=self.path.parent, suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
        except (OSError, Timeout):
            raise QueryError('群观战记录保存失败，原有对局未变更，请稍后重试') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def delete(self, group):
        group = group_id(group)
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, FileLock(str(self.path) + '.lock', timeout=3):
                data = self._read()
                if data.pop(group, None) is None:
                    return False
                encoded = json.dumps(data, ensure_ascii=False, sort_keys=True).encode('utf-8')
                with tempfile.NamedTemporaryFile(dir=self.path.parent, suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                return True
        except (OSError, Timeout):
            raise QueryError('群观战记录删除失败，原有对局未变更，请稍后重试') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
