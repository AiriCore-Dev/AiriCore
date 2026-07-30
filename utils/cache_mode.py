import threading

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
