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

TTL_AVATAR = 7 * 24 * 3600

_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "airi_daily_check"
_CACHE_FILE = _DATA_DIR / "cache.pk"

_FLUSH_INTERVAL = 3.0

_MAX_IMAGES = 64

_lock = threading.Lock()

_persist: dict = {}
_decoded: dict = {}
_persist_loaded = False
_last_flush = 0.0
_dirty = False

_images: "OrderedDict[str, Image.Image]" = OrderedDict()
_fonts: dict = {}


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
    k = (namespace, str(key))
    with _lock:
        _ensure_loaded()
        entry = _persist.get(namespace, {}).get(str(key))
        if entry is None:
            return None
        if ttl is not None and time.time() - entry["ts"] > ttl:
            return None
        cached = _decoded.get(k)
        if cached is not None:
            return cached
        blob = entry["blob"]
    value = _decode(blob)
    if value is not None:
        with _lock:
            _decoded[k] = value
    return value


def put(namespace: str, key: str, value: Any) -> None:
    global _dirty
    blob = _encode(value)
    if blob is None:
        return
    with _lock:
        _ensure_loaded()
        _persist.setdefault(namespace, {})[str(key)] = {"v": "", "ts": time.time(), "blob": blob}
        _decoded[(namespace, str(key))] = value
        _dirty = True
        _flush()


def get_or_build(namespace: str, key, build, stat_path=None) -> Any:
    global _dirty
    dkey = (namespace, key)
    with _lock:
        _ensure_loaded()
        cached = _decoded.get(dkey)
        if cached is not None:
            return cached
        entry = _persist.get(namespace, {}).get(key)
        if stat_path is None:
            version = entry["v"] if entry is not None else ""
            blob = entry["blob"] if entry is not None else None
        else:
            version = _version_of(stat_path)
            if entry is not None and entry["v"] == version:
                blob = entry["blob"]
            else:
                blob = None
    if blob is not None:
        value = _decode(blob)
        if value is not None:
            with _lock:
                _decoded[dkey] = value
            return value
    value = build()
    blob = _encode(value)
    with _lock:
        _decoded[dkey] = value
        if blob is not None:
            _persist.setdefault(namespace, {})[key] = {"v": version, "ts": time.time(), "blob": blob}
            _dirty = True
            _flush()
    return value


def get_image(path: str) -> Image.Image:
    with _lock:
        img = _images.get(path)
        if img is not None:
            _images.move_to_end(path)
            return img
    img = Image.open(path).convert("RGBA")
    with _lock:
        _images[path] = img
        _images.move_to_end(path)
        while len(_images) > _MAX_IMAGES:
            _images.popitem(last=False)
    return img


def get_image_copy(path: str) -> Image.Image:
    return get_image(path).copy()


def get_font(path: str, size: int):
    key = (path, size)
    with _lock:
        f = _fonts.get(key)
    if f is not None:
        return f
    f = ImageFont.truetype(font=path, size=size)
    with _lock:
        _fonts[key] = f
    return f
