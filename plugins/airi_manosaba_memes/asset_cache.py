import hashlib
import sys
import threading
from pathlib import Path

from sketchbook import Bitmap, FontSet

from utils.cache import ByteLRU, get_cache_budget_bytes, is_balanced, is_disk, register_asset_group, register_cache

from .utils import get_png_size


_bitmaps = ByteLRU(get_cache_budget_bytes("images"), owner="manosaba.bitmaps")
_fonts = ByteLRU(get_cache_budget_bytes("fonts"), owner="manosaba.fonts")
_renders = ByteLRU(get_cache_budget_bytes("base64"), owner="manosaba.renders")
_metadata = ByteLRU(32 * 1024 * 1024, owner="manosaba.metadata")
_lock = threading.RLock()

for _name, _cache in (("bitmaps", _bitmaps), ("fonts", _fonts), ("renders", _renders), ("metadata", _metadata)):
    register_cache(f"manosaba.{_name}", _cache)


def clear() -> None:
    with _lock:
        for cache in (_bitmaps, _fonts, _renders, _metadata):
            cache.clear()


def _signature(path: Path):
    stat = path.stat()
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size


def _get_or_load(cache, key, loader, cost):
    with _lock:
        if is_disk():
            clear()
        else:
            cache.probationary = is_balanced()
            cached = cache.get(key)
            if cached is not None:
                return cached
    value = loader()
    with _lock:
        if not is_disk():
            cache.put(key, value, cost(value) if callable(cost) else cost)
    return value


def get_bitmap(path) -> Bitmap:
    path = Path(path)
    width, height = get_png_size(path)
    return _get_or_load(_bitmaps, _signature(path), lambda: Bitmap.load(str(path)), width * height * 4)


def get_fonts(path) -> FontSet:
    path = Path(path)
    fonts = _get_or_load(_fonts, _signature(path), lambda: FontSet(str(path)), path.stat().st_size * 3)
    fonts.clear_cache()
    return fonts


def get_source(path) -> bytes:
    path = Path(path)
    return _get_or_load(_renders, ("source", _signature(path)), path.read_bytes, len)


def metadata_size(value, seen=None) -> int:
    seen = set() if seen is None else seen
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        return size + sum(metadata_size(key, seen) + metadata_size(item, seen) for key, item in value.items())
    if isinstance(value, (tuple, list, set, frozenset)):
        return size + sum(metadata_size(item, seen) for item in value)
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return size + metadata_size(vars(value), seen)
    return size


def get_metadata(key, loader):
    return _get_or_load(_metadata, key, loader, metadata_size)


def get_render(descriptor: str, loader) -> bytes:
    key = hashlib.sha256(descriptor.encode("utf-8")).hexdigest()
    return _get_or_load(_renders, key, loader, len)


def _preload_bitmap(path: Path) -> int:
    get_bitmap(path)
    width, height = get_png_size(path)
    return width * height * 4


register_asset_group("魔裁位图", Path(__file__).parent / "assets", ("*.png",), _preload_bitmap)
