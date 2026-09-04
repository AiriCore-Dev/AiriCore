import os
import threading

import numpy as np
from PIL import Image

from utils.cache import (
    get_cache_budget_bytes,
    is_balanced,
    is_disk,
    is_ram,
    register_cache,
)
from utils.cache import register_asset_group
from utils.cache import ByteLRU

_lock = threading.Lock()
_arrays = ByteLRU(get_cache_budget_bytes("arrays"), owner="kokomi.arrays")

register_cache("kokomi.arrays", _arrays)


def _preload_array(path):
    return int(get_array(path).nbytes)


_RESOURCE_ROOT = os.path.dirname(__file__)
for _name in ("ship_icon", "nation", "achievement", "achievement_plus", "clan", "list", "cw"):
    register_asset_group(f"kokomi {_name}", os.path.join(_RESOURCE_ROOT, "png", _name), ("*.png", "*.jpg", "*.jpeg"), _preload_array)


def _signature(path):
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _configure():
    _arrays.max_bytes = 0 if is_ram() else get_cache_budget_bytes("arrays")
    _arrays.probationary = is_balanced()


def _decode(path) -> np.ndarray:
    with Image.open(path) as pil_img:
        if pil_img.mode == "RGBA":
            arr = np.array(pil_img)
            return arr[:, :, [2, 1, 0, 3]].copy()
        if pil_img.mode == "LA":
            arr = np.array(pil_img.convert("RGBA"))
            return arr[:, :, [2, 1, 0, 3]].copy()
        if pil_img.mode == "P":
            if "transparency" in pil_img.info:
                arr = np.array(pil_img.convert("RGBA"))
                return arr[:, :, [2, 1, 0, 3]].copy()
            arr = np.array(pil_img.convert("RGB"))
            return arr[:, :, ::-1].copy()
        if pil_img.mode == "L":
            return np.array(pil_img).copy()
        arr = np.array(pil_img.convert("RGB"))
        return arr[:, :, ::-1].copy()


def get_array(path) -> np.ndarray:
    key = str(path)
    if is_disk():
        _arrays.clear()
        return _decode(key)
    _configure()
    signature = _signature(key)
    with _lock:
        cached = _arrays.get(key)
        if cached is not None:
            cached_signature, array = cached
            if cached_signature == signature:
                return array.copy()
            _arrays.pop(key, None)
    array = _decode(key)
    with _lock:
        _arrays.put(key, (signature, array), int(array.nbytes))
    return array.copy()
