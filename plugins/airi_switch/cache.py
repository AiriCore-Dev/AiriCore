
import copy
import pickle
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from nonebot import logger

from utils.cache_mode import is_disk

TTL_NAME = 3 * 24 * 3600
TTL_AVATAR = 7 * 24 * 3600

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "airi_switch"
_CACHE_FILE = _DATA_DIR / "meta_cache.pk"

_FLUSH_INTERVAL = 3.0

_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}
_last_flush = 0.0
_dirty = False


def _load() -> None:
    global _cache
    if is_disk():
        _cache = {}
        return
    if _CACHE_FILE.is_file():
        try:
            with open(_CACHE_FILE, "rb") as f:
                _cache = pickle.load(f)
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
        entry = _cache.get(kind, {}).get(str(key))
        if entry is None:
            return None
        value, ts = entry
        if ttl is not None and time.time() - ts > ttl:
            return None
        return value


def put(kind: str, key: str, value: Any) -> None:
    global _dirty
    if is_disk():
        return
    with _lock:
        _cache.setdefault(kind, {})[str(key)] = (value, time.time())
        _dirty = True
        _flush()


def flush() -> None:
    with _lock:
        _flush(force=True)


_load()
