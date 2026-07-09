import time
import pickle
import threading
from pathlib import Path
from typing import Optional

from nonebot.log import logger

# 头像缓存有效期：3 天
TTL_AVATAR = 3 * 24 * 3600

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nonebot_plugin_today_waifu"
_CACHE_FILE = _DATA_DIR / "cache.pk"

_FLUSH_INTERVAL = 3.0

_lock = threading.Lock()

_persist: dict = {}
_persist_loaded = False
_last_flush = 0.0
_dirty = False


def _ensure_loaded() -> None:
    global _persist, _persist_loaded
    if _persist_loaded:
        return
    _persist_loaded = True
    if _CACHE_FILE.is_file():
        try:
            with open(_CACHE_FILE, "rb") as f:
                _persist = pickle.load(f)
            return
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>today_waifu cache.pk 读取失败，已重置: {e}</y>")
    _persist = {}


def _flush(force: bool = False) -> None:
    global _last_flush, _dirty
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


def get_avatar(uid: str) -> Optional[bytes]:
    """命中且未过期返回头像 bytes，否则 None。"""
    with _lock:
        _ensure_loaded()
        entry = _persist.get("avatar", {}).get(str(uid))
        if entry is None:
            return None
        if time.time() - entry["ts"] > TTL_AVATAR:
            return None
        return entry["blob"]


def put_avatar(uid: str, data: bytes) -> None:
    global _dirty
    if not data:
        return
    with _lock:
        _ensure_loaded()
        _persist.setdefault("avatar", {})[str(uid)] = {"ts": time.time(), "blob": data}
        _dirty = True
        _flush()
