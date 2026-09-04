
import copy
import pickle
import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from nonebot import logger

from utils.cache import is_disk, register_preload

TTL_NAME = 2 * 3600
TTL_AVATAR = 7 * 24 * 3600

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "airi_switch"
_CACHE_FILE = _DATA_DIR / "meta_cache.pk"

_FLUSH_INTERVAL = 30.0
_PURGE_INTERVAL = 300.0
_MAX_PER_KIND = {
    "user_avatar": 800,
    "group_avatar": 800,
    "bot_name": 5000,
    "group_name": 5000,
}
_MAX_PER_KIND_DEFAULT = 5000
_MAX_BYTES_PER_KIND = {
    "user_avatar": 64 * 1024 * 1024,
    "group_avatar": 64 * 1024 * 1024,
    "bot_name": 2 * 1024 * 1024,
    "group_name": 8 * 1024 * 1024,
}
_KIND_TTL = {
    "user_avatar": TTL_AVATAR,
    "group_avatar": TTL_AVATAR,
    "bot_name": TTL_NAME,
    "group_name": TTL_NAME,
}

_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}
_last_flush = 0.0
_last_purge = 0.0
_dirty = False


def _value_bytes(value) -> int:
    if isinstance(value, (bytes, bytearray, str)):
        return len(value)
    return sys.getsizeof(value)


def _purge_unlocked(force: bool = False) -> None:
    global _last_purge, _dirty
    now = time.time()
    if not force and now - _last_purge < _PURGE_INTERVAL:
        return
    _last_purge = now
    for kind, entries in list(_cache.items()):
        if not isinstance(entries, dict):
            continue
        ttl = _KIND_TTL.get(kind, TTL_NAME)
        for key in [k for k, v in entries.items()
                    if not (isinstance(v, tuple) and len(v) == 2) or now - v[1] > ttl]:
            entries.pop(key, None)
            _dirty = True
        cap = _MAX_PER_KIND.get(kind, _MAX_PER_KIND_DEFAULT)
        max_bytes = _MAX_BYTES_PER_KIND.get(kind, 16 * 1024 * 1024)
        while len(entries) > cap or (
            max_bytes and sum(_value_bytes(v[0]) for v in entries.values()) > max_bytes
        ):
            ordered = sorted(entries.items(), key=lambda kv: kv[1][1])
            for key, _ in ordered[:1]:
                entries.pop(key, None)
                _dirty = True


def _load() -> None:
    global _cache
    if is_disk():
        _cache = {}
        return
    if _CACHE_FILE.is_file():
        try:
            with open(_CACHE_FILE, "rb") as f:
                _cache = pickle.load(f)
            _purge_unlocked(force=True)
            return
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>airi_switch 元信息缓存读取失败,已重置: {e}</y>")
    _cache = {}


def _flush(force: bool = False) -> None:
    global _last_flush, _dirty
    if is_disk():
        return
    now = time.time()
    if not force and (not _dirty or now - _last_flush < _FLUSH_INTERVAL):
        return
    _purge_unlocked(force=force)
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_FILE.with_suffix(".pk.tmp")
        with open(tmp, "wb") as f:
            pickle.dump(_cache, f)
        tmp.replace(_CACHE_FILE)
        _last_flush = now
        _dirty = False
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>airi_switch 元信息缓存写入失败: {e}</y>")


def get(kind: str, key: str, ttl: Optional[float] = None) -> Any:
    if is_disk():
        return None
    with _lock:
        bucket = _cache.get(kind, {})
        entry = bucket.get(str(key))
        if entry is None:
            return None
        value, ts = entry
        if ttl is not None and time.time() - ts > ttl:
            bucket.pop(str(key), None)
            return None
        return value


def put(kind: str, key: str, value: Any) -> None:
    global _dirty
    if is_disk():
        return
    with _lock:
        bucket = _cache.setdefault(kind, {})
        bucket[str(key)] = (value, time.time())
        _dirty = True
        cap = _MAX_PER_KIND.get(kind, _MAX_PER_KIND_DEFAULT)
        if len(bucket) > cap * 2:
            _purge_unlocked(force=True)
        _flush()


def flush() -> None:
    with _lock:
        _flush(force=True)


def preload(max_bytes: int = 0):
    if is_disk():
        return 0, 0
    with _lock:
        if not _cache:
            _load()
        _purge_unlocked(force=True)
        items = 0
        used = 0
        for entries in _cache.values():
            if not isinstance(entries, dict):
                continue
            items += len(entries)
            for v in entries.values():
                val = v[0] if isinstance(v, tuple) and v else v
                if isinstance(val, (bytes, bytearray, str)):
                    used += len(val)
    return items, used


_load()
register_preload("airi_switch 元信息", preload)
