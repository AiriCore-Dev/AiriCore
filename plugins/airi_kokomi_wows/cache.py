import os
import threading
from collections import OrderedDict

import numpy as np
from PIL import Image

from utils.cache_mode import is_disk, is_ram

_MAX_ARRAYS = 128

_lock = threading.Lock()
_arrays: "OrderedDict[str, tuple]" = OrderedDict()


def _decode(path) -> np.ndarray:
    pil_img = Image.open(path)
    if pil_img.mode == 'RGBA':
        arr = np.array(pil_img)
        return arr[:, :, [2, 1, 0, 3]].copy()
    elif pil_img.mode == 'LA':
        arr = np.array(pil_img.convert('RGBA'))
        return arr[:, :, [2, 1, 0, 3]].copy()
    elif pil_img.mode == 'P':
        if 'transparency' in pil_img.info:
            arr = np.array(pil_img.convert('RGBA'))
            return arr[:, :, [2, 1, 0, 3]].copy()
        arr = np.array(pil_img.convert('RGB'))
        return arr[:, :, ::-1].copy()
    elif pil_img.mode == 'L':
        return np.array(pil_img).copy()
    else:
        arr = np.array(pil_img.convert('RGB'))
        return arr[:, :, ::-1].copy()


def _sig(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def get_array(path) -> np.ndarray:
    key = str(path)
    if is_disk():
        return _decode(key)
    sig = _sig(key)
    with _lock:
        entry = _arrays.get(key)
        if entry is not None and entry[0] == sig:
            _arrays.move_to_end(key)
            return entry[1].copy()
    arr = _decode(key)
    with _lock:
        _arrays[key] = (sig, arr)
        _arrays.move_to_end(key)
        if not is_ram():
            while len(_arrays) > _MAX_ARRAYS:
                _arrays.popitem(last=False)
    return arr.copy()
