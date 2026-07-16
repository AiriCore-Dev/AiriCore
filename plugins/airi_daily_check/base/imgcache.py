
import threading
from collections import OrderedDict

from PIL import Image, ImageFont

_MAX_IMAGES = 64

_lock = threading.Lock()
_images: "OrderedDict[str, Image.Image]" = OrderedDict()
_fonts = {}


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
