import base64
import os
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageFont

_VALID = ("ram", "balanced", "disk")
_DEFAULT = "balanced"
_DEFAULT_BUDGET_MB = 4096

_CACHE_BUDGETS = {
    "images": 128 * 1024 * 1024,
    "arrays": 256 * 1024 * 1024,
    "base64": 64 * 1024 * 1024,
    "decoded": 128 * 1024 * 1024,
    "fonts": 16 * 1024 * 1024,
}

_lock = threading.Lock()
_mode = None
_budget_mb = None
_cache_registry = {}
_ram_allocations = {}
_ram_used = 0


def _resolve() -> str:
    try:
        from nonebot import get_driver

        raw = getattr(get_driver().config, "cache_mode", None)
    except Exception:
        raw = None
    if raw is None:
        return _DEFAULT
    val = str(raw).strip().lower()
    if val not in _VALID:
        return _DEFAULT
    return val


def get_mode() -> str:
    global _mode
    if _mode is not None:
        return _mode
    with _lock:
        if _mode is None:
            _mode = _resolve()
        return _mode


def is_ram() -> bool:
    return get_mode() == "ram"


def is_balanced() -> bool:
    return get_mode() == "balanced"


def is_disk() -> bool:
    return get_mode() == "disk"


def _resolve_budget_mb() -> int:
    try:
        from nonebot import get_driver

        raw = getattr(get_driver().config, "cache_preload_budget_mb", None)
    except Exception:
        raw = None
    if raw is None:
        return _DEFAULT_BUDGET_MB
    try:
        val = int(str(raw).strip())
    except Exception:
        return _DEFAULT_BUDGET_MB
    if val <= 0:
        return 0
    return val


def get_preload_budget_mb() -> int:
    global _budget_mb
    if _budget_mb is not None:
        return _budget_mb
    with _lock:
        if _budget_mb is None:
            _budget_mb = _resolve_budget_mb()
        return _budget_mb


def get_preload_budget_bytes() -> int:
    return get_preload_budget_mb() * 1024 * 1024


def get_cache_budget_bytes(kind: str) -> int:
    return _CACHE_BUDGETS.get(str(kind), 64 * 1024 * 1024)


def register_cache(name: str, cache) -> None:
    with _lock:
        _cache_registry[str(name)] = cache


def get_cache_stats():
    with _lock:
        items = list(_cache_registry.items())
    result = {}
    for name, cache in items:
        try:
            result[name] = cache.stats()
        except Exception:
            continue
    return result


def reset_ram_budget() -> None:
    global _ram_allocations, _ram_used
    with _lock:
        _ram_allocations = {}
        _ram_used = 0


def reserve_ram(owner: str, key, size: int) -> bool:
    global _ram_used
    if not is_ram():
        return True
    limit = get_preload_budget_bytes()
    token = (str(owner), key)
    size = max(0, int(size))
    with _lock:
        previous = _ram_allocations.get(token, 0)
        if limit > 0 and _ram_used - previous + size > limit:
            return False
        _ram_used = _ram_used - previous + size
        _ram_allocations[token] = size
        return True


def release_ram(owner: str, key) -> None:
    global _ram_used
    token = (str(owner), key)
    with _lock:
        previous = _ram_allocations.pop(token, 0)
        _ram_used = max(0, _ram_used - previous)


def get_ram_resident_bytes() -> int:
    with _lock:
        return _ram_used

def value_bytes(value) -> int:
    if isinstance(value, (bytes, bytearray, str)):
        return len(value)
    nbytes = getattr(value, "nbytes", None)
    if nbytes is not None:
        try:
            return max(0, int(nbytes))
        except (TypeError, ValueError):
            pass
    size = getattr(value, "size", None)
    mode = getattr(value, "mode", None)
    if isinstance(size, tuple) and len(size) == 2 and isinstance(mode, str):
        try:
            return max(0, int(size[0]) * int(size[1]) * len(mode))
        except (TypeError, ValueError):
            pass
    if isinstance(value, (tuple, list)):
        return sum(value_bytes(item) for item in value)
    return max(0, sys.getsizeof(value))


class ByteLRU:

    def __init__(self, max_bytes: int, probationary: bool = False, seen_limit: int = 4096, owner: str = ""):
        self.max_bytes = max(0, int(max_bytes))
        self.probationary = probationary
        self.seen_limit = max(1, int(seen_limit))
        self.owner = owner
        self._data = OrderedDict()
        self._seen = OrderedDict()
        self._bytes = 0
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.admissions = 0
        self.skips = 0

    @property
    def bytes(self) -> int:
        with self._lock:
            return self._bytes

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def get(self, key, default=None):
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return default
            self._data.move_to_end(key)
            self.hits += 1
            return item[0]

    def put(self, key, value, cost: int = None) -> bool:
        cost = value_bytes(value) if cost is None else max(0, int(cost))
        with self._lock:
            if self.max_bytes and cost > self.max_bytes:
                self._seen.pop(key, None)
                self.skips += 1
                return False
            if self.probationary and key not in self._data and key not in self._seen:
                self._seen[key] = None
                self._seen.move_to_end(key)
                while len(self._seen) > self.seen_limit:
                    self._seen.popitem(last=False)
                self.skips += 1
                return False
            if self.owner:

                if not reserve_ram(self.owner, key, cost):
                    self.skips += 1
                    return False
            self._seen.pop(key, None)
            old = self._data.pop(key, None)
            if old is not None:
                self._bytes -= old[1]
            while self.max_bytes and self._data and self._bytes + cost > self.max_bytes:
                old_key, (_, old_cost) = self._data.popitem(last=False)
                self._bytes -= old_cost
                if self.owner:
                    release_ram(self.owner, old_key)
                self.evictions += 1
            if self.max_bytes and self._bytes + cost > self.max_bytes:
                if self.owner:
                    release_ram(self.owner, key)
                self.skips += 1
                return False
            self._data[key] = (value, cost)
            self._bytes += cost
            self.admissions += 1
            return True

    def pop(self, key, default=None):
        with self._lock:
            item = self._data.pop(key, None)
            self._seen.pop(key, None)
            if item is None:
                return default
            self._bytes -= item[1]
            if self.owner:
                release_ram(self.owner, key)
            return item[0]

    def clear(self) -> None:
        with self._lock:
            keys = list(self._data.keys())
            self._data.clear()
            self._seen.clear()
            self._bytes = 0
            if self.owner:
                for key in keys:
                    release_ram(self.owner, key)

    def keys(self):
        with self._lock:
            return list(self._data.keys())

    def stats(self):
        with self._lock:
            return {
                "items": len(self._data),
                "bytes": self._bytes,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "admissions": self.admissions,
                "skips": self.skips,
                "probation": len(self._seen),
            }

_asset_lock = threading.Lock()
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
    with _asset_lock:
        cached = _images.get(key)
        if cached is not None:
            cached_signature, image = cached
            if cached_signature == signature:
                return image
            _images.pop(key, None)
    image = Image.open(key).convert("RGBA")
    with _asset_lock:
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
    with _asset_lock:
        cached = _fonts.get(key)
        if cached is not None:
            cached_signature, font = cached
            if cached_signature == signature:
                return font
            _fonts.pop(key, None)
    font = ImageFont.truetype(font=str(path), size=size, index=index, encoding=encoding)
    with _asset_lock:
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
    with _asset_lock:
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
    with _asset_lock:
        _b64.put(key, (signature, data), len(data))
    return data

_PRELOADERS: Dict[str, Any] = {}
_ASSET_GROUPS: List[Dict[str, Any]] = []


def register_preload(name: str, callback) -> None:
    _PRELOADERS[str(name)] = callback


def register_asset_group(name: str, directory, patterns, loader, *, preload=True, recursive=True) -> None:
    group = {
        "label": str(name),
        "dir": Path(directory),
        "patterns": tuple(patterns),
        "loader": loader,
        "preload": bool(preload),
        "recursive": bool(recursive),
    }
    _ASSET_GROUPS[:] = [item for item in _ASSET_GROUPS if item["label"] != group["label"]]
    _ASSET_GROUPS.append(group)


class Budget:

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0
        self.estimated = 0
        self.skipped = 0
        self.reasons = {}

    def ok(self) -> bool:
        return self.limit <= 0 or self.used < self.limit

    def can_fit(self, n: int) -> bool:
        return self.limit <= 0 or self.used + max(0, int(n)) <= self.limit

    def add(self, n: int, estimate: int = None) -> None:
        self.used += max(0, int(n))
        self.estimated += max(0, int(n if estimate is None else estimate))

    def skip(self, n: int = 1, reason: str = "budget") -> None:
        self.skipped += n
        self.reasons[reason] = self.reasons.get(reason, 0) + n


def _iter_files(base: Path, patterns, recursive: bool = True) -> List[Path]:
    if not base.is_dir():
        return []
    out: List[Path] = []
    globber = base.rglob if recursive else base.glob
    for pat in patterns:
        try:
            out.extend(p for p in globber(pat) if p.is_file())
        except Exception:
            continue
    return sorted(set(out))


def _image_bytes(img) -> int:
    try:
        w, h = img.size
        return w * h * len(img.mode)
    except Exception:
        return 0


def _decoded_channels(pil_img) -> int:
    if pil_img.mode == "L":
        return 1
    if pil_img.mode == "P" and "transparency" not in pil_img.info:
        return 3
    return 4


def _estimate_file(path: Path, loader) -> int:
    if loader is _load_shared_image:
        try:
            with Image.open(path) as image:
                return image.width * image.height * _decoded_channels(image)
        except Exception:
            return 0
    if loader is _load_shared_b64:
        try:
            return 9 + ((path.stat().st_size + 2) // 3) * 4
        except OSError:
            return 0
    try:
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
            with Image.open(path) as image:
                return image.width * image.height * _decoded_channels(image)
        return 9 + ((path.stat().st_size + 2) // 3) * 4
    except (OSError, ValueError):
        return 0
    return 0


def _load_shared_image(path: Path) -> int:
    from utils import cache as asset_cache

    return _image_bytes(asset_cache.get_image(path))


def _load_shared_b64(path: Path) -> int:
    from utils import cache as asset_cache

    data = asset_cache.get_b64(path)
    return len(data) if data else 0


def _preload_pk_caches(budget: Budget) -> List[Dict[str, Any]]:
    results = []
    for label, fn in sorted(_PRELOADERS.items()):
        entry = {"label": label, "items": 0, "bytes": 0}
        try:
            if not budget.ok():
                entry["error"] = "预算已用尽, 跳过"
                budget.skip(reason="budget")
            else:
                remain = budget.limit - budget.used if budget.limit > 0 else -1
                items, used = fn(remain)
                entry["items"] = int(items)
                entry["bytes"] = int(used)
                if budget.limit > 0 and used > remain:
                    entry["skipped"] = int(items)
                    entry["reason"] = "budget"
                    budget.skip(int(items), reason="budget")
                    entry["bytes"] = 0
                else:
                    budget.add(used, used)
        except Exception as e:
            entry["error"] = str(e)
        results.append(entry)
    return results


def _preload_assets(budget: Budget) -> List[Dict[str, Any]]:
    results = []
    for group in _ASSET_GROUPS:
        base = group["dir"]
        files = _iter_files(base, group["patterns"], group.get("recursive", True))
        if not files:
            continue
        entry = {"label": group["label"], "items": 0, "bytes": 0, "skipped": 0}
        loader = group["loader"]
        if not group.get("preload", True):
            entry["skipped"] = len(files)
            entry["reason"] = "cold_group"
            budget.skip(len(files), reason="cold_group")
            results.append(entry)
            continue
        for path in files:
            estimate = _estimate_file(path, loader)
            if not budget.can_fit(estimate):
                entry["skipped"] += 1
                budget.skip(reason="budget")
                continue
            try:
                used = loader(path)
            except Exception:
                continue
            if budget.limit > 0 and used > budget.limit - budget.used:
                entry["skipped"] += 1
                budget.skip(reason="budget")
                continue
            entry["items"] += 1
            entry["bytes"] += used
            budget.add(used, estimate)
        results.append(entry)
    return results


_summary: Dict[str, Any] = {}


def get_summary() -> Dict[str, Any]:
    return _summary


def run() -> Dict[str, Any]:
    global _summary
    started = time.time()
    mode = get_mode()
    if not is_ram():
        _summary = {"mode": mode, "enabled": False, "groups": [], "items": 0,
                    "bytes": 0, "estimated_bytes": 0, "skipped": 0,
                    "skip_reasons": {}, "seconds": 0.0}
        return _summary

    budget = Budget(get_preload_budget_bytes())
    groups: List[Dict[str, Any]] = []
    groups.extend(_preload_pk_caches(budget))
    groups.extend(_preload_assets(budget))

    items = sum(g.get("items", 0) for g in groups)
    _summary = {
        "mode": mode,
        "enabled": True,
        "groups": groups,
        "items": items,
        "bytes": budget.used,
        "estimated_bytes": budget.estimated,
        "skipped": budget.skipped,
        "skip_reasons": dict(budget.reasons),
        "budget_bytes": budget.limit,
        "seconds": round(time.time() - started, 2),
    }
    return _summary


def _fmt(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    kb = n / 1024
    if kb < 1024:
        return f"{kb:.1f}KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f}MB"
    return f"{mb / 1024:.2f}GB"


def run_and_log() -> Dict[str, Any]:
    from nonebot.log import logger

    try:
        s = run()
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>缓存预热失败: {e}</y>")
        return {}
    if not s.get("enabled"):
        logger.info(f"缓存模式 {s.get('mode')}，跳过启动预热")
        return s
    logger.info(
        f"缓存预热完成: {s['items']} 项 / {_fmt(s['bytes'])} / {s['seconds']}s"
        f"（上限 {_fmt(s['budget_bytes'])}）"
    )
    if s["skipped"]:
        logger.opt(colors=True).warning(
            f"<y>缓存预热达到内存上限，跳过 {s['skipped']} 项；"
            f"可调大 .env.prod 的 cache_preload_budget_mb</y>"
        )
    return s
