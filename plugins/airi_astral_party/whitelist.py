import json
import os
import re
import tempfile
import threading
from pathlib import Path

from filelock import FileLock, Timeout

from .protocol import QueryError


def group_id(value):
    if not re.fullmatch(r'[0-9]{1,19}', str(value)) or not 0 < int(value) < 2**63:
        raise QueryError('群号应为有效的正整数：astral 验证码 whitelist 群号')
    return str(int(value))


class GroupWhitelist:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _read(self):
        try:
            if not self.path.exists():
                return set()
            if self.path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, list):
                raise ValueError
            return {group_id(value) for value in data}
        except (OSError, ValueError, TypeError, QueryError):
            raise QueryError('吉星派对群白名单损坏或不可读，请联系管理员；原文件已保留') from None

    def allows(self, group):
        group = group_id(group)
        with self._lock:
            return group in self._read()

    def add(self, group):
        group = group_id(group)
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, FileLock(str(self.path) + '.lock', timeout=3):
                groups = self._read()
                if group in groups:
                    return False
                groups.add(group)
                encoded = json.dumps(sorted(groups, key=int), ensure_ascii=False).encode('utf-8')
                if len(encoded) > 2 * 1024 * 1024:
                    raise QueryError('群白名单已达容量上限，请联系管理员')
                with tempfile.NamedTemporaryFile(dir=self.path.parent, suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                return True
        except (OSError, Timeout):
            raise QueryError('群白名单保存失败，原有名单未变更，请稍后重试') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
