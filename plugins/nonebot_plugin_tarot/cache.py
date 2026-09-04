import base64
import io
import os
import pickle
import threading
import time
from pathlib import Path
from typing import Optional

from nonebot.log import logger
from PIL import Image

from utils.cache import is_disk, register_preload

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nonebot_plugin_tarot"
_CACHE_FILE = _DATA_DIR / "cache.pk"

_FLUSH_INTERVAL = 3.0
_PERSIST_MAX_BYTES = 128 * 1024 * 1024
_MAX_ENTRIES = 64

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
    return sum(_entry_bytes(entry) for entry in _persist.get("card", {}).values())


def _purge_unlocked() -> None:
    global _dirty
    card = _persist.get("card", {})
    if not isinstance(card, dict):
        _persist["card"] = {}
        _dirty = True
        return
    for key, entry in list(card.items()):
        if not isinstance(entry, dict) or not isinstance(entry.get("b64"), str):
            card.pop(key, None)
            _dirty = True
    while len(card) > _MAX_ENTRIES or (_PERSIST_MAX_BYTES and _persist_bytes() > _PERSIST_MAX_BYTES):
        key, _ = min(card.items(), key=lambda item: item[1].get("ts", 0))
        card.pop(key, None)
        _dirty = True


def _ensure_loaded() -> None:
    global _persist, _persist_loaded
    if _persist_loaded:
        return
    _persist_loaded = True
    _persist = {}
    if is_disk():
        return
    try:
        if not _CACHE_FILE.is_file():
            return
        if _PERSIST_MAX_BYTES and _CACHE_FILE.stat().st_size > _PERSIST_MAX_BYTES:
            logger.warning("tarot cache.pk 超过缓存上限，跳过加载")
            return
        with open(_CACHE_FILE, "rb") as file:
            loaded = pickle.load(file)
        if isinstance(loaded, dict) and isinstance(loaded.get("card", {}), dict):
            _persist = {"card": dict(loaded.get("card", {}))}
            _purge_unlocked()
    except Exception as error:
        logger.opt(colors=True).warning(f"<y>tarot cache.pk load failed, reset: {error}</y>")


def _flush(force: bool = False) -> None:
    global _last_flush, _dirty
    if is_disk():
        return
    now = time.time()
    if not force and (not _dirty or now - _last_flush < _FLUSH_INTERVAL):
        return
    _purge_unlocked()
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_FILE.with_suffix(".pk.tmp")
        with open(tmp, "wb") as file:
            pickle.dump(_persist, file)
        tmp.replace(_CACHE_FILE)
        _last_flush = now
        _dirty = False
    except Exception as error:
        logger.opt(colors=True).warning(f"<y>tarot cache.pk write failed: {error}</y>")


def flush() -> None:
    with _lock:
        _flush(force=True)


def _sig(path: Path):
    try:
        stat = path.stat()
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _source_b64(path: Path) -> Optional[str]:
    try:
        with open(path, "rb") as file:
            return "base64://" + base64.b64encode(file.read()).decode()
    except OSError:
        return None


def _encode(path: Path, reversed_: bool) -> Optional[str]:
    if not reversed_:
        return _source_b64(path)
    try:
        with Image.open(path) as image:
            rotated = image.rotate(180)
            buffer = io.BytesIO()
            rotated.save(buffer, format="png")
        return "base64://" + base64.b64encode(buffer.getvalue()).decode()
    except Exception as error:
        logger.opt(colors=True).warning(f"tarot encode {path} failed: {error}")
        return None


def preload(max_bytes: int = 0):
    if is_disk():
        return 0, 0
    with _lock:
        _ensure_loaded()
        card = _persist.get("card", {})
        return len(card), _persist_bytes()


def get_card_b64(path, reversed_: bool) -> Optional[str]:
    global _dirty
    path = Path(path)
    signature = _sig(path)
    if signature is None:
        return None
    key = f"{path}\x00{int(reversed_)}"
    if is_disk():
        return _encode(path, reversed_)
    with _lock:
        _ensure_loaded()
        entry = _persist.get("card", {}).get(key)
        if isinstance(entry, dict) and entry.get("sig") == signature and isinstance(entry.get("b64"), str):
            return entry["b64"]
    b64 = _encode(path, reversed_)
    if b64 is None:
        return None
    with _lock:
        _ensure_loaded()
        card = _persist.setdefault("card", {})
        existing = card.get(key)
        if isinstance(existing, dict) and existing.get("sig") == signature and isinstance(existing.get("b64"), str):
            return existing["b64"]
        card[key] = {"sig": signature, "b64": b64, "ts": time.time()}
        _purge_unlocked()
        _dirty = True
        _flush()
    return b64


register_preload("tarot 牌面", preload)
