import time
import pickle
import threading
from pathlib import Path
from typing import Optional

from nonebot.log import logger

from utils.cache import is_disk, register_preload

TTL_AVATAR = 3 * 24 * 3600

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nonebot_plugin_today_waifu"
_CACHE_FILE = _DATA_DIR / "cache.pk"

_FLUSH_INTERVAL = 3.0
_MAX_PERSIST_BYTES = 64 * 1024 * 1024
_MAX_ENTRIES = 800

_lock = threading.Lock()

_persist: dict = {}
_persist_loaded = False
_last_flush = 0.0
_dirty = False


def _entry_bytes(entry) -> int:
    if not isinstance(entry, dict):
        return 0
    blob = entry.get("blob")
    return len(blob) if isinstance(blob, (bytes, bytearray)) else 0


def _persist_bytes() -> int:
    return sum(_entry_bytes(entry) for entry in _persist.get("avatar", {}).values())


def _purge_unlocked() -> None:
    global _dirty
    bucket = _persist.get("avatar", {})
    if not isinstance(bucket, dict):
        _persist["avatar"] = {}
        _dirty = True
        return
    for key, entry in list(bucket.items()):
        if not isinstance(entry, dict) or not isinstance(entry.get("blob"), (bytes, bytearray)):
            bucket.pop(key, None)
            _dirty = True
    while len(bucket) > _MAX_ENTRIES or (_MAX_PERSIST_BYTES and _persist_bytes() > _MAX_PERSIST_BYTES):
        key, _ = min(bucket.items(), key=lambda item: item[1].get("ts", 0))
        bucket.pop(key, None)
        _dirty = True


def _ensure_loaded() -> None:
    global _persist, _persist_loaded
    if _persist_loaded:
        return
    _persist_loaded = True
    if is_disk():
        _persist = {}
        return
    if _CACHE_FILE.is_file():
        try:
            if _MAX_PERSIST_BYTES and _CACHE_FILE.stat().st_size > _MAX_PERSIST_BYTES:
                logger.warning("today_waifu cache.pk 超过缓存上限，跳过加载")
                return
            with open(_CACHE_FILE, "rb") as f:
                _persist = pickle.load(f)
            _purge_unlocked()
            return
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>today_waifu cache.pk 读取失败，已重置: {e}</y>")
    _persist = {}


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
            pickle.dump(_persist, f)
        tmp.replace(_CACHE_FILE)
        _last_flush = now
        _dirty = False
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>today_waifu cache.pk 写入失败: {e}</y>")


def flush() -> None:
    with _lock:
        _flush(force=True)


def preload(max_bytes: int = 0):
    if is_disk():
        return 0, 0
    with _lock:
        _ensure_loaded()
        bucket = _persist.get("avatar", {}) or {}
        used = 0
        for entry in bucket.values():
            blob = entry.get("blob") if isinstance(entry, dict) else None
            if blob:
                used += len(blob)
        return len(bucket), used


def get_avatar(uid: str) -> Optional[bytes]:
    global _dirty
    if is_disk():
        return None
    with _lock:
        _ensure_loaded()
        bucket = _persist.get("avatar", {})
        entry = bucket.get(str(uid))
        if entry is None:
            return None
        if time.time() - entry["ts"] > TTL_AVATAR:
            bucket.pop(str(uid), None)
            _dirty = True
            _flush()
            return None
        return entry["blob"]


def put_avatar(uid: str, data: bytes) -> None:
    global _dirty
    if is_disk():
        return
    if not data:
        return
    with _lock:
        _ensure_loaded()
        _persist.setdefault("avatar", {})[str(uid)] = {"ts": time.time(), "blob": data}
        _purge_unlocked()
        _dirty = True
        _flush()


register_preload("today_waifu 头像", preload)
