import asyncio
import json
import os
from pathlib import Path
import pickle
import shutil
import tempfile
import time

from nonebot import logger

from .models import GameState


class _PlainUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        raise pickle.UnpicklingError(f"存档包含不允许的对象：{module}.{name}")


class GameStore:
    def __init__(self, path: Path):
        self.path = path
        self.backup_path = path.with_suffix(path.suffix + ".bak")
        self.legacy_path = path.with_suffix(".json")
        self.legacy_backup_path = self.legacy_path.with_suffix(
            self.legacy_path.suffix + ".bak"
        )
        self._save_lock = asyncio.Lock()

    async def load(self) -> dict[str, GameState]:
        if self.path.exists() or self.backup_path.exists():
            return await self._load_current()
        if self.legacy_path.exists() or self.legacy_backup_path.exists():
            return await self._migrate_legacy()
        return {}

    async def _load_current(self) -> dict[str, GameState]:
        if self.path.exists():
            try:
                return await asyncio.to_thread(self._read_pickle, self.path)
            except Exception as primary_error:
                logger.error(f"得分沙拉主存档读取失败：{primary_error}")
        if self.backup_path.exists():
            try:
                games = await asyncio.to_thread(
                    self._read_pickle, self.backup_path
                )
                logger.warning("得分沙拉已从备份存档恢复")
                return games
            except Exception as backup_error:
                logger.error(f"得分沙拉备份存档读取失败：{backup_error}")
        await self._quarantine(self.path, self.path.suffix)
        return {}

    async def _migrate_legacy(self) -> dict[str, GameState]:
        games = None
        if self.legacy_path.exists():
            try:
                games = await asyncio.to_thread(
                    self._read_json, self.legacy_path
                )
            except Exception as primary_error:
                logger.error(f"得分沙拉旧版主存档读取失败：{primary_error}")
        if games is None and self.legacy_backup_path.exists():
            try:
                games = await asyncio.to_thread(
                    self._read_json, self.legacy_backup_path
                )
            except Exception as backup_error:
                logger.error(f"得分沙拉旧版备份存档读取失败：{backup_error}")
        if games is None:
            await self._quarantine(self.legacy_path, self.legacy_path.suffix)
            return {}
        await self.save(games)
        logger.warning("得分沙拉旧版 JSON 存档已迁移为 pickle 存档")
        return games

    async def _quarantine(self, path: Path, suffix: str) -> None:
        if not path.exists():
            return
        quarantine = path.with_name(
            time.strftime(f"games.corrupt.%Y%m%dT%H%M%S{suffix}")
        )
        try:
            await asyncio.to_thread(os.replace, path, quarantine)
            logger.error(f"得分沙拉坏档已隔离为 {quarantine.name}")
        except OSError as error:
            logger.error(f"得分沙拉坏档隔离失败：{error}")

    async def save(self, games: dict[str, GameState]) -> None:
        async with self._save_lock:
            payload = {group_id: state.to_dict() for group_id, state in games.items()}
            await asyncio.to_thread(self._write_atomic, payload)

    def _read_pickle(self, path: Path) -> dict[str, GameState]:
        with path.open("rb") as file:
            payload = _PlainUnpickler(file).load()
        return self._decode(payload)

    def _read_json(self, path: Path) -> dict[str, GameState]:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file, parse_constant=self._reject_constant)
        return self._decode(payload)

    def _decode(self, payload) -> dict[str, GameState]:
        if type(payload) is not dict:
            raise TypeError("存档根节点必须是对象")
        return {
            self._group_id(group_id): GameState.from_dict(state)
            for group_id, state in payload.items()
        }

    def _write_atomic(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=".games-",
            suffix=self.path.suffix,
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(fd, "wb") as file:
                pickle.dump(payload, file, protocol=pickle.HIGHEST_PROTOCOL)
                file.flush()
                os.fsync(file.fileno())
            if self.path.exists():
                shutil.copyfile(self.path, self.backup_path)
            os.replace(temporary_path, self.path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _reject_constant(value: str):
        raise ValueError(f"存档包含非法数值：{value}")

    @staticmethod
    def _group_id(value) -> str:
        if type(value) is not str:
            raise TypeError("群号键必须是字符串")
        return value
