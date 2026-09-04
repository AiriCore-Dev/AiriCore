import asyncio
import os
from pathlib import Path
import pickle
import shutil
import tempfile
import time

from nonebot import logger

from .models import GameState


PAYLOAD_VERSION = 2


class _PlainUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        raise pickle.UnpicklingError(f"存档包含不允许的对象：{module}.{name}")


class GameStore:
    def __init__(self, path: Path):
        self.path = path
        self.backup_path = path.with_suffix(path.suffix + ".bak")
        self._save_lock = asyncio.Lock()

    async def load(self) -> dict[str, GameState]:
        if self.path.exists() or self.backup_path.exists():
            return await self._load_current()
        return {}

    async def _load_current(self) -> dict[str, GameState]:
        primary_error = None
        if self.path.exists():
            try:
                games = await asyncio.to_thread(self._read_pickle, self.path)
                return games
            except Exception as error:
                primary_error = error
                logger.error(f"得分沙拉主存档读取失败：{error}")
        if self.backup_path.exists():
            try:
                games = await asyncio.to_thread(
                    self._read_pickle, self.backup_path
                )
                if primary_error is not None:
                    await self._quarantine(self.path, self.path.suffix)
                logger.warning("得分沙拉已从备份存档恢复")
                return games
            except Exception as backup_error:
                logger.error(f"得分沙拉备份存档读取失败：{backup_error}")
        if primary_error is not None:
            await self._quarantine(self.path, self.path.suffix)
        return {}

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
            payload = _encode(games)
            await asyncio.to_thread(self._write_atomic, payload)

    def _read_pickle(self, path: Path) -> dict[str, GameState]:
        with path.open("rb") as file:
            payload = _PlainUnpickler(file).load()
        return self._decode(payload)

    def _decode(self, payload) -> dict[str, GameState]:
        if type(payload) is not dict:
            raise TypeError("存档根节点必须是对象")
        if set(payload) != {"schema_version", "games"}:
            raise ValueError("存档根节点字段不匹配")
        if type(payload["schema_version"]) is not int:
            raise TypeError("存档版本必须是整数")
        if payload["schema_version"] != PAYLOAD_VERSION:
            raise ValueError("不支持的存档版本")
        games = payload["games"]
        if type(games) is not dict:
            raise TypeError("games 必须是对象")
        return {
            self._group_id(group_id): GameState.from_dict(state)
            for group_id, state in games.items()
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


def _encode(games: dict[str, GameState]) -> dict:
    if type(games) is not dict:
        raise TypeError("games 必须是对象")
    return {
        "schema_version": PAYLOAD_VERSION,
        "games": {
            GameStore._group_id(group_id): state.to_dict()
            for group_id, state in games.items()
        },
    }
