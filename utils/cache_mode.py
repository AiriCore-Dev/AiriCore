import threading

_VALID = ("ram", "balanced", "disk")
_DEFAULT = "balanced"
_DEFAULT_BUDGET_MB = 4096

_lock = threading.Lock()
_mode = None
_budget_mb = None


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
