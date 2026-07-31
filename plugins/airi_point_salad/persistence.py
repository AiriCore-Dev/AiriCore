import asyncio
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from nonebot import logger

from .models import GameState


class GameStore:
    def __init__(self, path: Path):
        self.path = path
        self.backup_path = path.with_suffix(path.suffix + ".bak")
        self._save_lock = asyncio.Lock()

    async def load(self) -> dict[str, GameState]:
        if not self.path.exists():
            return {}
        try:
            return await asyncio.to_thread(self._read, self.path)
        except Exception as primary_error:
            logger.error(f"得分沙拉主存档读取失败：{primary_error}")
        if self.backup_path.exists():
            try:
                games = await asyncio.to_thread(self._read, self.backup_path)
                logger.warning("得分沙拉已从备份存档恢复")
                return games
            except Exception as backup_error:
                logger.error(f"得分沙拉备份存档读取失败：{backup_error}")
        quarantine = self.path.with_name(time.strftime("games.corrupt.%Y%m%dT%H%M%S.json"))
        try:
            await asyncio.to_thread(os.replace, self.path, quarantine)
            logger.error(f"得分沙拉坏档已隔离为 {quarantine.name}")
        except OSError as error:
            logger.error(f"得分沙拉坏档隔离失败：{error}")
        return {}

    async def save(self, games: dict[str, GameState]) -> None:
        async with self._save_lock:
            payload = {group_id: state.to_dict() for group_id, state in games.items()}
            await asyncio.to_thread(self._write_atomic, payload)

    def _read(self, path: Path) -> dict[str, GameState]:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file, parse_constant=self._reject_constant)
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
            suffix=".json",
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(
                    payload,
                    file,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
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
