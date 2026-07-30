import sys
import threading
from collections import OrderedDict


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
                from utils.cache_mode import reserve_ram

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
                    from utils.cache_mode import release_ram

                    release_ram(self.owner, old_key)
                self.evictions += 1
            if self.max_bytes and self._bytes + cost > self.max_bytes:
                if self.owner:
                    from utils.cache_mode import release_ram

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
                from utils.cache_mode import release_ram

                release_ram(self.owner, key)
            return item[0]

    def clear(self) -> None:
        with self._lock:
            keys = list(self._data.keys())
            self._data.clear()
            self._seen.clear()
            self._bytes = 0
            if self.owner:
                from utils.cache_mode import release_ram

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
