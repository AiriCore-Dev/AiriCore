import time
from collections import deque

_buckets: dict = {}
_MAX_KEYS = 20000


def _prune(now: float) -> None:
    if len(_buckets) <= _MAX_KEYS:
        return
    for key in [k for k, dq in _buckets.items() if not dq or now - dq[-1] > 3600]:
        _buckets.pop(key, None)
    if len(_buckets) > _MAX_KEYS:
        _buckets.clear()


def allow(key: str, limit: int, window: float) -> bool:
    now = time.time()
    dq = _buckets.get(key)
    if dq is None:
        dq = deque()
        _buckets[key] = dq
        _prune(now)
    while dq and now - dq[0] > window:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True


def retry_after(key: str, window: float) -> int:
    dq = _buckets.get(key)
    if not dq:
        return 0
    return max(1, int(window - (time.time() - dq[0])))
