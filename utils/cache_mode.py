import threading

_VALID = ("ram", "balanced", "disk")
_DEFAULT = "balanced"

_lock = threading.Lock()
_mode = None


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
