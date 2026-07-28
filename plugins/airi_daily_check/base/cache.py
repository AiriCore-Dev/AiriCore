import os
import time
import pickle
import threading
from io import BytesIO
from pathlib import Path
from collections import OrderedDict
from typing import Any, Optional

from PIL import Image, ImageFont
from nonebot.log import logger

from utils.cache_mode import is_disk, is_ram

TTL_AVATAR = 7 * 24 * 3600

_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "airi_daily_check"
_CACHE_FILE = _DATA_DIR / "cache.pk"

_FLUSH_INTERVAL = 3.0

_MAX_IMAGES = 64
_MAX_DECODED = 256
_MAX_PERSIST_PER_NS = 600
_NS_TTL = {"avatar": TTL_AVATAR}
_DEFAULT_NS_TTL = 7 * 24 * 3600
_PURGE_INTERVAL = 300.0

_lock = threading.Lock()

_persist: dict = {}
_decoded: "OrderedDict[tuple, Any]" = OrderedDict()
_persist_loaded = False
_last_flush = 0.0
_last_purge = 0.0
_dirty = False

_images: "OrderedDict[str, Image.Image]" = OrderedDict()
_fonts: dict = {}


def _touch_decoded(dkey, value) -> None:
    _decoded[dkey] = value
    _decoded.move_to_end(dkey)
    if not is_ram():
        while len(_decoded) > _MAX_DECODED:
            _decoded.popitem(last=False)


def _purge_unlocked(force: bool = False) -> None:
    global _last_purge, _dirty
    now = time.time()
    if not force and now - _last_purge < _PURGE_INTERVAL:
        return
    _last_purge = now
    for namespace, bucket in list(_persist.items()):
        if not isinstance(bucket, dict):
            continue
        ttl = _NS_TTL.get(namespace, _DEFAULT_NS_TTL)
        for key in [
            k for k, v in bucket.items()
            if not isinstance(v, dict) or now - v.get("ts", 0) > ttl
        ]:
            bucket.pop(key, None)
            _decoded.pop((namespace, key), None)
            _dirty = True
        if len(bucket) > _MAX_PERSIST_PER_NS:
            ordered = sorted(bucket.items(), key=lambda kv: kv[1].get("ts", 0))
            for key, _ in ordered[: len(bucket) - _MAX_PERSIST_PER_NS]:
                bucket.pop(key, None)
                _decoded.pop((namespace, key), None)
                _dirty = True


def _encode(value) -> Optional[bytes]:
    if isinstance(value, bytes):
        return b"B" + value
    if isinstance(value, str):
        return b"S" + value.encode("utf-8")
    if isinstance(value, Image.Image):
        buf = BytesIO()
        value.save(buf, format="PNG")
        return b"I" + buf.getvalue()
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], Image.Image):
        buf = BytesIO()
        value[0].save(buf, format="PNG")
        return b"T" + buf.getvalue()
    return None


def _decode(blob: bytes):
    tag, body = blob[:1], blob[1:]
    if tag == b"B":
        return body
    if tag == b"S":
        return body.decode("utf-8")
    if tag == b"I":
        return Image.open(BytesIO(body)).convert("RGBA")
    if tag == b"T":
        img = Image.open(BytesIO(body)).convert("RGBA")
        return img, img.split()[3]
    return None


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
            logger.opt(colors=True).warning(f"<y>airi_daily_check cache.pk 读取失败，已重置: {e}</y>")
    _persist = {}


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
            pickle.dump(_persist, f)
        tmp.replace(_CACHE_FILE)
        _last_flush = now
        _dirty = False
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>airi_daily_check cache.pk 写入失败: {e}</y>")


def flush() -> None:
    with _lock:
        _flush(force=True)


def _version_of(stat_path) -> str:
    if not stat_path:
        return ""
    try:
        st = os.stat(stat_path)
        return f"{st.st_mtime_ns}-{st.st_size}"
    except OSError:
        return ""


def get(namespace: str, key: str, ttl: Optional[float] = None) -> Any:
    if is_disk():
        return None
    k = (namespace, str(key))
    with _lock:
        _ensure_loaded()
        bucket = _persist.get(namespace, {})
        entry = bucket.get(str(key))
        if entry is None:
            return None
        if ttl is not None and time.time() - entry["ts"] > ttl:
            bucket.pop(str(key), None)
            _decoded.pop(k, None)
            return None
        cached = _decoded.get(k)
        if cached is not None:
            _decoded.move_to_end(k)
            return cached
        blob = entry["blob"]
    value = _decode(blob)
    if value is not None:
        with _lock:
            _touch_decoded(k, value)
    return value


def put(namespace: str, key: str, value: Any) -> None:
    global _dirty
    if is_disk():
        return
    blob = _encode(value)
    if blob is None:
        return
    with _lock:
        _ensure_loaded()
        _persist.setdefault(namespace, {})[str(key)] = {"v": "", "ts": time.time(), "blob": blob}
        _touch_decoded((namespace, str(key)), value)
        _dirty = True
        _flush()


def get_or_build(namespace: str, key, build, stat_path=None) -> Any:
    global _dirty
    if is_disk():
        return build()
    dkey = (namespace, key)
    version = "" if stat_path is None else _version_of(stat_path)
    with _lock:
        _ensure_loaded()
        entry = _persist.get(namespace, {}).get(key)
        stale = stat_path is not None and (entry is None or entry["v"] != version)
        if stale:
            _decoded.pop(dkey, None)
            blob = None
        else:
            cached = _decoded.get(dkey)
            if cached is not None:
                _decoded.move_to_end(dkey)
                return cached
            if stat_path is None:
                version = entry["v"] if entry is not None else ""
            blob = entry["blob"] if entry is not None else None
    if blob is not None:
        value = _decode(blob)
        if value is not None:
            with _lock:
                _touch_decoded(dkey, value)
            return value
    value = build()
    blob = _encode(value)
    with _lock:
        _touch_decoded(dkey, value)
        if blob is not None:
            _persist.setdefault(namespace, {})[key] = {"v": version, "ts": time.time(), "blob": blob}
            _dirty = True
            _flush()
    return value


def _value_bytes(value) -> int:
    if isinstance(value, (bytes, bytearray, str)):
        return len(value)
    if isinstance(value, Image.Image):
        try:
            w, h = value.size
            return w * h * len(value.mode)
        except Exception:
            return 0
    if isinstance(value, tuple) and value:
        return sum(_value_bytes(v) for v in value)
    return 0


def preload(max_bytes: int = 0):
    if is_disk():
        return 0, 0
    with _lock:
        _ensure_loaded()
        _purge_unlocked(force=True)
        pending = []
        for namespace, bucket in _persist.items():
            if not isinstance(bucket, dict):
                continue
            for key, entry in bucket.items():
                if not isinstance(entry, dict):
                    continue
                blob = entry.get("blob")
                if blob is None:
                    continue
                dkey = (namespace, key)
                if dkey in _decoded:
                    continue
                pending.append((dkey, blob))

    items = 0
    used = 0
    for dkey, blob in pending:
        if max_bytes > 0 and used >= max_bytes:
            break
        try:
            value = _decode(blob)
        except Exception:
            continue
        if value is None:
            continue
        with _lock:
            _touch_decoded(dkey, value)
        items += 1
        used += _value_bytes(value)
    return items, used


def get_image(path: str) -> Image.Image:
    if is_disk():
        return Image.open(path).convert("RGBA")
    with _lock:
        img = _images.get(path)
        if img is not None:
            _images.move_to_end(path)
            return img
    img = Image.open(path).convert("RGBA")
    with _lock:
        _images[path] = img
        _images.move_to_end(path)
        if not is_ram():
            while len(_images) > _MAX_IMAGES:
                _images.popitem(last=False)
    return img


def get_image_copy(path: str) -> Image.Image:
    return get_image(path).copy()


def get_font(path: str, size: int):
    if is_disk():
        return ImageFont.truetype(font=path, size=size)
    key = (path, size)
    with _lock:
        f = _fonts.get(key)
    if f is not None:
        return f
    f = ImageFont.truetype(font=path, size=size)
    with _lock:
        _fonts[key] = f
    return f
