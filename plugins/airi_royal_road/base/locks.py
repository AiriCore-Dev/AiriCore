from __future__ import annotations

import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class _Record:
    lock: asyncio.Lock
    waiters: int = 0
    last_use: float = 0.0


class _Registry:
    def __init__(self, ttl: float = 300.0):
        self.records: dict[str, _Record] = {}
        self.ttl = ttl

    def record(self, key: str) -> _Record:
        now = time.monotonic()
        record = self.records.get(key)
        if record is None:
            record = _Record(asyncio.Lock(), 0, now)
            self.records[key] = record
        record.waiters += 1
        record.last_use = now
        return record

    def cleanup(self) -> None:
        now = time.monotonic()
        stale = [key for key, record in self.records.items() if record.waiters == 0 and not record.lock.locked() and now - record.last_use >= self.ttl]
        for key in stale:
            self.records.pop(key, None)


_users = _Registry()
_world = _Registry()
_settlements = _Registry()


@asynccontextmanager
async def _acquire(registry: _Registry, key: str):
    record = registry.record(str(key))
    try:
        await record.lock.acquire()
        yield
    finally:
        if record.lock.locked():
            record.lock.release()
        record.waiters -= 1
        record.last_use = time.monotonic()
        registry.cleanup()


def user_lock(user_id: str):
    return _acquire(_users, user_id)


def world_lock(week_id: int | str):
    return _acquire(_world, week_id)


def settlement_lock(user_id: str):
    return _acquire(_settlements, user_id)


def event_id(scope: str, user_id: str, date_key: str, step_key: str) -> str:
    value = "|".join(str(item).strip() for item in (scope, user_id, date_key, step_key))
    return hashlib.sha256(value.encode("ascii", "strict")).hexdigest()


def cleanup_locks() -> None:
    _users.cleanup()
    _world.cleanup()
    _settlements.cleanup()
