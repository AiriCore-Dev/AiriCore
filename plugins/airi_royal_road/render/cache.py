from __future__ import annotations

from collections import OrderedDict


class RenderCache:
    def __init__(self, byte_budget: int = 16 * 1024 * 1024):
        self.byte_budget = byte_budget
        self._items: OrderedDict[tuple, bytes] = OrderedDict()
        self._size = 0

    def get(self, key: tuple) -> bytes | None:
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
            return bytes(value)
        return None

    def put(self, key: tuple, value: bytes) -> bytes:
        value = bytes(value)
        previous = self._items.pop(key, None)
        if previous is not None:
            self._size -= len(previous)
        self._items[key] = value
        self._size += len(value)
        while self._size > self.byte_budget and self._items:
            _, removed = self._items.popitem(last=False)
            self._size -= len(removed)
        return bytes(value)

    def clear(self) -> None:
        self._items.clear()
        self._size = 0
