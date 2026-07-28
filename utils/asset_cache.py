import base64
import threading
from collections import OrderedDict
from typing import Optional

from PIL import Image, ImageFont

from utils.cache_mode import is_disk, is_ram

_MAX_IMAGES = 64
_MAX_FONTS = 128
_MAX_B64 = 256

_lock = threading.Lock()
_images: "OrderedDict[str, Image.Image]" = OrderedDict()
_fonts: "OrderedDict[tuple, object]" = OrderedDict()
_b64: "OrderedDict[str, str]" = OrderedDict()


def get_image(path) -> Image.Image:
    key = str(path)
    if is_disk():
        return Image.open(key).convert("RGBA")
    with _lock:
        img = _images.get(key)
        if img is not None:
            _images.move_to_end(key)
            return img
    img = Image.open(key).convert("RGBA")
    with _lock:
        _images[key] = img
        _images.move_to_end(key)
        if not is_ram():
            while len(_images) > _MAX_IMAGES:
                _images.popitem(last=False)
    return img


def get_image_copy(path) -> Image.Image:
    return get_image(path).copy()


def get_font(path, size: int, index: int = 0, encoding: str = ""):
    if is_disk():
        return ImageFont.truetype(font=str(path), size=size, index=index, encoding=encoding)
    key = (str(path), size, index, encoding)
    with _lock:
        f = _fonts.get(key)
        if f is not None:
            _fonts.move_to_end(key)
    if f is not None:
        return f
    f = ImageFont.truetype(font=str(path), size=size, index=index, encoding=encoding)
    with _lock:
        _fonts[key] = f
        _fonts.move_to_end(key)
        if not is_ram():
            while len(_fonts) > _MAX_FONTS:
                _fonts.popitem(last=False)
    return f


def get_b64(path) -> Optional[str]:
    key = str(path)
    if is_disk():
        try:
            with open(key, "rb") as f:
                return "base64://" + base64.b64encode(f.read()).decode()
        except OSError:
            return None
    with _lock:
        cached = _b64.get(key)
        if cached is not None:
            _b64.move_to_end(key)
    if cached is not None:
        return cached
    try:
        with open(key, "rb") as f:
            data = "base64://" + base64.b64encode(f.read()).decode()
    except OSError:
        return None
    with _lock:
        _b64[key] = data
        _b64.move_to_end(key)
        if not is_ram():
            while len(_b64) > _MAX_B64:
                _b64.popitem(last=False)
    return data
