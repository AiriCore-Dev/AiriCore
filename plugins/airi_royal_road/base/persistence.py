from __future__ import annotations

import asyncio
import os
import pickle
import shutil
import time
from pathlib import Path
from typing import Any

from nonebot import logger

from .constants import PERSONAL_DATA_FILE, PERSONAL_DATA_KEY, SCHEMA_VERSION, WORLD_DATA_FILE, WORLD_DATA_KEY


class PlainUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        raise pickle.UnpicklingError("存档包含不允许的对象")


def _plain(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_plain(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _plain(item) for key, item in value.items())
    return False


class Store:
    def __init__(self, path: Path, root_key: str):
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self.root_key = root_key
        self._lock = asyncio.Lock()
        self._state: dict[str, Any] = {}
        self._initialized = False

    async def initialize(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict) or not _plain(state):
            raise TypeError("初始存档必须是纯字典")
        async with self._lock:
            self._state = dict(state)
            self._initialized = True

    async def load(self) -> dict[str, Any]:
        async with self._lock:
            errors = []
            for candidate in (self.path, self.backup_path):
                if not candidate.exists():
                    continue
                try:
                    payload = await asyncio.to_thread(self._read, candidate)
                    state = payload[self.root_key]
                    self._state = dict(state)
                    self._initialized = True
                    if candidate == self.backup_path and self.path != candidate:
                        await asyncio.to_thread(shutil.copyfile, candidate, self.path)
                    return dict(self._state)
                except Exception as exc:
                    errors.append((candidate, exc))
                    await self._quarantine(candidate)
            if self._initialized and not errors:
                return dict(self._state)
            if self._initialized and errors and not self.path.exists() and not self.backup_path.exists():
                raise RuntimeError("存档损坏且没有可恢复备份")
            if errors:
                raise RuntimeError("存档损坏且没有可恢复备份")
            return dict(self._state)

    async def save(self, state: dict[str, Any] | None = None) -> None:
        async with self._lock:
            candidate = self._state if state is None else state
            if not isinstance(candidate, dict) or not _plain(candidate):
                raise TypeError("存档必须是纯字典")
            payload = {"schema_version": SCHEMA_VERSION, self.root_key: dict(candidate)}
            if self.path.exists():
                await asyncio.to_thread(shutil.copyfile, self.path, self.backup_path)
            await asyncio.to_thread(self._atomic_write, payload)
            await asyncio.to_thread(shutil.copyfile, self.path, self.backup_path)
            self._state = dict(candidate)
            self._initialized = True

    async def flush(self) -> None:
        await self.save()

    def _read(self, path: Path) -> dict[str, Any]:
        with path.open("rb") as stream:
            payload = PlainUnpickler(stream).load()
        if not isinstance(payload, dict) or set(payload) != {"schema_version", self.root_key}:
            raise ValueError("存档结构无效")
        if payload["schema_version"] != SCHEMA_VERSION or not isinstance(payload[self.root_key], dict) or not _plain(payload[self.root_key]):
            raise ValueError("存档版本或内容无效")
        return payload

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f".{self.path.name}.{os.getpid()}.{time.time_ns()}.tmp")
        try:
            with temp_path.open("wb") as stream:
                pickle.dump(payload, stream, protocol=pickle.HIGHEST_PROTOCOL)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    async def _quarantine(self, path: Path) -> None:
        if not path.exists():
            return
        target = path.with_name(f"{path.name}.broken.{time.time_ns()}")
        await asyncio.to_thread(os.replace, path, target)
        logger.error(f"王道征途坏档已隔离：{target.name}")


class PersonalStore(Store):
    def __init__(self, path: Path = PERSONAL_DATA_FILE):
        super().__init__(path, PERSONAL_DATA_KEY)


class WorldStore(Store):
    def __init__(self, path: Path = WORLD_DATA_FILE):
        super().__init__(path, WORLD_DATA_KEY)


personal_store = PersonalStore()
world_store = WorldStore()
