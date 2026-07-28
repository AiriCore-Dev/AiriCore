import io
import time
import base64
import pickle
import threading
from pathlib import Path
from typing import Optional

from nonebot.log import logger
from PIL import Image

from utils.cache_mode import is_disk

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nonebot_plugin_tarot"
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
            logger.opt(colors=True).warning(f"<y>tarot cache.pk load failed, reset: {e}</y>")
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
        logger.opt(colors=True).warning(f"<y>tarot cache.pk write failed: {e}</y>")


def flush() -> None:
    with _lock:
        _flush(force=True)


def _sig(path: Path):
    try:
        st = path.stat()
    except OSError:
        return None
    return (int(st.st_mtime_ns), st.st_size)


def _encode(path: Path, reversed_: bool) -> Optional[str]:
    try:
        img: Image.Image = Image.open(path)
        if reversed_:
            img = img.rotate(180)
        buf = io.BytesIO()
        img.save(buf, format="png")
        return "base64://" + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>tarot encode {path} failed: {e}</y>")
        return None


def preload(max_bytes: int = 0):
    if is_disk():
        return 0, 0
    with _lock:
        _ensure_loaded()
        bucket = _persist.get("card", {}) or {}
        used = 0
        for entry in bucket.values():
            b64 = entry.get("b64") if isinstance(entry, dict) else None
            if b64:
                used += len(b64)
        return len(bucket), used


def get_card_b64(path, reversed_: bool) -> Optional[str]:
    global _dirty
    path = Path(path)
    sig = _sig(path)
    if sig is None:
        return None
    key = f"{path}\x00{int(reversed_)}"
    if is_disk():
        return _encode(path, reversed_)
    with _lock:
        _ensure_loaded()
        card = _persist.setdefault("card", {})
        entry = card.get(key)
        if entry is not None and entry["sig"] == sig:
            return entry["b64"]
    b64 = _encode(path, reversed_)
    if b64 is None:
        return None
    with _lock:
        _ensure_loaded()
        _persist.setdefault("card", {})[key] = {"sig": sig, "b64": b64}
        _dirty = True
        _flush()
    return b64
