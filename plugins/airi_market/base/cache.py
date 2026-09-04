import pickle
import threading
import time
from pathlib import Path
from typing import Optional

from nonebot.log import logger

from utils.cache import is_disk, register_preload

_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "airi_market"
_CACHE_FILE = _DATA_DIR / "cache.pk"

_FLUSH_INTERVAL = 3.0
_MAX_PERSIST_BYTES = 64 * 1024 * 1024
_MAX_ENTRIES = 256

_lock = threading.Lock()
_persist: dict = {}
_persist_loaded = False
_last_flush = 0.0
_dirty = False
_legacy_oversized = False


def _entry_bytes(entry) -> int:
    if not isinstance(entry, dict):
        return 0
    try:
        return len(pickle.dumps(entry.get("data"), protocol=pickle.HIGHEST_PROTOCOL))
    except Exception:
        return 0


def _persist_bytes() -> int:
    return sum(_entry_bytes(entry) for entry in _persist.get("articles", {}).values())


def _purge_unlocked() -> None:
    global _dirty
    bucket = _persist.get("articles", {})
    if not isinstance(bucket, dict):
        _persist["articles"] = {}
        _dirty = True
        return
    for key, entry in list(bucket.items()):
        if not isinstance(entry, dict) or not isinstance(entry.get("data"), dict):
            bucket.pop(key, None)
            _dirty = True
    while len(bucket) > _MAX_ENTRIES or (_MAX_PERSIST_BYTES and _persist_bytes() > _MAX_PERSIST_BYTES):
        key, _ = min(bucket.items(), key=lambda item: item[1].get("ts", 0))
        bucket.pop(key, None)
        _dirty = True


def _ensure_loaded() -> None:
    global _persist, _persist_loaded, _legacy_oversized
    if _persist_loaded:
        return
    _persist_loaded = True
    if is_disk():
        _persist = {}
        return
    if _CACHE_FILE.is_file():
        try:
            if _MAX_PERSIST_BYTES and _CACHE_FILE.stat().st_size > _MAX_PERSIST_BYTES:
                _legacy_oversized = True
                logger.warning("airi_market cache.pk 超过缓存上限，跳过旧缓存并在下次写入时收敛")
                return
            with open(_CACHE_FILE, "rb") as f:
                _persist = pickle.load(f)
            _purge_unlocked()
            return
        except Exception as e:
            logger.opt(colors=True).warning(
                f"<y>airi_market cache.pk load failed, reset: {e}</y>"
            )
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
        logger.opt(colors=True).warning(
            f"<y>airi_market cache.pk write failed: {e}</y>"
        )


def flush() -> None:
    with _lock:
        _flush(force=True)


def _sig(path: Path):
    try:
        st = path.stat()
        return (int(st.st_mtime_ns), st.st_size)
    except OSError:
        return None


def preload(max_bytes: int = 0):
    if is_disk():
        return 0, 0
    with _lock:
        _ensure_loaded()
        if _legacy_oversized:
            return 0, 0
        return len(_persist.get("articles", {}) or {}), 0


def get_article(article_name: str, index_path: Path) -> Optional[dict]:
    if is_disk():
        return None
    sig = _sig(index_path)
    if sig is None:
        return None
    with _lock:
        _ensure_loaded()
        entry = _persist.get("articles", {}).get(article_name)
        if entry is not None and entry["sig"] == sig:
            return entry["data"]
    return None


def put_article(article_name: str, index_path: Path, data: dict) -> None:
    global _dirty
    if is_disk():
        return
    sig = _sig(index_path)
    if sig is None:
        return
    with _lock:
        _ensure_loaded()
        _persist.setdefault("articles", {})[article_name] = {"sig": sig, "data": data, "ts": time.time()}
        _purge_unlocked()
        _dirty = True
        _flush()


def invalidate_article(article_name: str) -> None:
    global _dirty
    with _lock:
        _ensure_loaded()
        if _persist.get("articles", {}).pop(article_name, None) is not None:
            _dirty = True
            _flush()


register_preload("airi_market 文章", preload)
