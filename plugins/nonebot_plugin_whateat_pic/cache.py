import time
import base64
import pickle
import threading
from pathlib import Path
from typing import Optional

from nonebot.log import logger

from utils.cache import is_disk, register_asset_group, register_preload

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nonebot_plugin_whateat_pic"
_CACHE_FILE = _DATA_DIR / "cache.pk"

_FLUSH_INTERVAL = 3.0
_MAX_PERSIST_BYTES = 64 * 1024 * 1024
_MAX_ENTRIES = 512

_lock = threading.Lock()

_persist: dict = {}
_persist_loaded = False
_last_flush = 0.0
_dirty = False


def _entry_bytes(entry) -> int:
    if not isinstance(entry, dict):
        return 0
    b64 = entry.get("b64")
    return len(b64) if isinstance(b64, str) else 0


def _persist_bytes() -> int:
    return sum(_entry_bytes(entry) for entry in _persist.get("img", {}).values())


def _purge_unlocked() -> None:
    global _dirty
    bucket = _persist.get("img", {})
    if not isinstance(bucket, dict):
        _persist["img"] = {}
        _dirty = True
        return
    for key, entry in list(bucket.items()):
        if not isinstance(entry, dict) or not isinstance(entry.get("b64"), str):
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
                logger.warning("whateat_pic cache.pk 超过缓存上限，跳过加载")
                return
            with open(_CACHE_FILE, "rb") as f:
                _persist = pickle.load(f)
            _purge_unlocked()
            return
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>whateat_pic cache.pk load failed, reset: {e}</y>")
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
        logger.opt(colors=True).warning(f"<y>whateat_pic cache.pk write failed: {e}</y>")


def flush() -> None:
    with _lock:
        _flush(force=True)


def _sig(path: Path):
    try:
        st = path.stat()
    except OSError:
        return None
    return (int(st.st_mtime_ns), st.st_size)


def preload(max_bytes: int = 0):
    if is_disk():
        return 0, 0
    with _lock:
        _ensure_loaded()
        bucket = _persist.get("img", {}) or {}
        used = 0
        for entry in bucket.values():
            b64 = entry.get("b64") if isinstance(entry, dict) else None
            if b64:
                used += len(b64)
        return len(bucket), used


def get_b64(path) -> Optional[str]:
    global _dirty
    path = Path(path)
    sig = _sig(path)
    if sig is None:
        return None
    key = str(path)
    if is_disk():
        try:
            with open(path, "rb") as f:
                return "base64://" + base64.b64encode(f.read()).decode()
        except OSError:
            return None
    with _lock:
        _ensure_loaded()
        img = _persist.setdefault("img", {})
        entry = img.get(key)
        if entry is not None and entry["sig"] == sig:
            return entry["b64"]
    try:
        with open(path, "rb") as f:
            b64 = "base64://" + base64.b64encode(f.read()).decode()
    except OSError:
        return None
    with _lock:
        _ensure_loaded()
        _persist.setdefault("img", {})[key] = {"sig": sig, "b64": b64, "ts": time.time()}
        _purge_unlocked()
        _dirty = True
        _flush()
    return b64


def invalidate(path) -> None:
    global _dirty
    key = str(Path(path))
    with _lock:
        _ensure_loaded()
        if _persist.get("img", {}).pop(key, None) is not None:
            _dirty = True
            _flush()


register_preload("whateat_pic 图片", preload)
register_asset_group("whateat 图片", Path(__file__).resolve().parent / "eat_pic", ("*.png", "*.jpg", "*.jpeg"), lambda path: len(get_b64(path) or ""))
register_asset_group("whateat 饮品", Path(__file__).resolve().parent / "drink_pic", ("*.png", "*.jpg", "*.jpeg"), lambda path: len(get_b64(path) or ""))
