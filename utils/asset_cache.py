import base64
import os
import threading

from PIL import Image, ImageFont

from utils.cache_mode import (
    get_cache_budget_bytes,
    is_balanced,
    is_disk,
    is_ram,
    register_cache,
)
from utils.cache_policy import ByteLRU, value_bytes

_lock = threading.Lock()
_images = ByteLRU(get_cache_budget_bytes("images"), owner="asset_cache.images")
_fonts = ByteLRU(get_cache_budget_bytes("fonts"), owner="asset_cache.fonts")
_b64 = ByteLRU(get_cache_budget_bytes("base64"), owner="asset_cache.base64")

register_cache("asset_cache.images", _images)
register_cache("asset_cache.fonts", _fonts)
register_cache("asset_cache.base64", _b64)


def _signature(path):
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _configure(cache, kind):
    cache.max_bytes = 0 if is_ram() else get_cache_budget_bytes(kind)
    cache.probationary = is_balanced()


def _clear_for_disk():
    _images.clear()
    _fonts.clear()
    _b64.clear()


def get_image(path) -> Image.Image:
    key = str(path)
    if is_disk():
        _clear_for_disk()
        return Image.open(key).convert("RGBA")
    _configure(_images, "images")
    signature = _signature(key)
    with _lock:
        cached = _images.get(key)
        if cached is not None:
            cached_signature, image = cached
            if cached_signature == signature:
                return image
            _images.pop(key, None)
    image = Image.open(key).convert("RGBA")
    with _lock:
        _images.put(key, (signature, image), value_bytes(image))
    return image


def get_image_copy(path) -> Image.Image:
    return get_image(path).copy()


def get_font(path, size: int, index: int = 0, encoding: str = ""):
    if is_disk():
        _clear_for_disk()
        return ImageFont.truetype(font=str(path), size=size, index=index, encoding=encoding)
    _configure(_fonts, "fonts")
    key = (str(path), int(size), int(index), encoding)
    signature = _signature(path)
    with _lock:
        cached = _fonts.get(key)
        if cached is not None:
            cached_signature, font = cached
            if cached_signature == signature:
                return font
            _fonts.pop(key, None)
    font = ImageFont.truetype(font=str(path), size=size, index=index, encoding=encoding)
    with _lock:
        _fonts.put(key, (signature, font), 256 * 1024)
    return font


def get_b64(path):
    key = str(path)
    if is_disk():
        _clear_for_disk()
        try:
            with open(key, "rb") as file:
                return "base64://" + base64.b64encode(file.read()).decode()
        except OSError:
            return None
    _configure(_b64, "base64")
    signature = _signature(key)
    with _lock:
        cached = _b64.get(key)
        if cached is not None:
            cached_signature, data = cached
            if cached_signature == signature:
                return data
            _b64.pop(key, None)
    try:
        with open(key, "rb") as file:
            data = "base64://" + base64.b64encode(file.read()).decode()
    except OSError:
        return None
    with _lock:
        _b64.put(key, (signature, data), len(data))
    return data
