import pickle
import threading
import time
from pathlib import Path
from typing import Optional

from nonebot.log import logger

from utils.cache_mode import is_disk

_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "airi_market"
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
    if is_disk():
        _persist = {}
        return
    if _CACHE_FILE.is_file():
        try:
            with open(_CACHE_FILE, "rb") as f:
                _persist = pickle.load(f)
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
        _persist.setdefault("articles", {})[article_name] = {"sig": sig, "data": data}
        _dirty = True
        _flush()


def invalidate_article(article_name: str) -> None:
    global _dirty
    with _lock:
        _ensure_loaded()
        if _persist.get("articles", {}).pop(article_name, None) is not None:
            _dirty = True
            _flush()
