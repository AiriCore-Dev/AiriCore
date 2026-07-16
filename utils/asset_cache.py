import base64
import threading
from collections import OrderedDict
from typing import Optional

from PIL import Image, ImageFont

from utils.cache_mode import is_disk, is_ram

_MAX_IMAGES = 64

_lock = threading.Lock()
_images: "OrderedDict[str, Image.Image]" = OrderedDict()
_fonts: dict = {}
_b64: dict = {}


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


def get_font(path, size: int):
    if is_disk():
        return ImageFont.truetype(font=str(path), size=size)
    key = (str(path), size)
    with _lock:
        f = _fonts.get(key)
    if f is not None:
        return f
    f = ImageFont.truetype(font=str(path), size=size)
    with _lock:
        _fonts[key] = f
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
        return cached
    try:
        with open(key, "rb") as f:
            data = "base64://" + base64.b64encode(f.read()).decode()
    except OSError:
        return None
    with _lock:
        _b64[key] = data
    return data
