import asyncio
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from ..runtime import logger, run_storage


SCHEMA_VERSION = 1


class BackgroundPickerContext(BaseModel):
    category: str
    page: int = 1
    codes: list[str] = Field(default_factory=list)


class BackgroundSessionData(BaseModel):
    schema_version: int = SCHEMA_VERSION
    messages: dict[str, BackgroundPickerContext] = Field(default_factory=dict)


class BackgroundSessionStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = BackgroundSessionData()
        self.lock = asyncio.Lock()
        self._loaded = False

    async def load(self) -> BackgroundSessionData:
        async with self.lock:
            if self._loaded:
                return self.data
            self.data = await run_storage(self._load_sync)
            self._loaded = True
            return self.data

    def _load_sync(self) -> BackgroundSessionData:
        if not self.path.exists():
            return BackgroundSessionData()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            version = raw.get("schema_version") if isinstance(raw, dict) else None
            if version != SCHEMA_VERSION:
                raise ValueError
            return BackgroundSessionData.model_validate(raw)
        except (ValueError, TypeError, json.JSONDecodeError):
            logger.warning("背景会话数据损坏，备份原文件后恢复空记录")
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            broken = self.path.with_name(f"{self.path.name}.broken.{timestamp}")
            counter = 1
            while broken.exists():
                broken = self.path.with_name(
                    f"{self.path.name}.broken.{timestamp}.{counter}"
                )
                counter += 1
            os.replace(self.path, broken)
            return BackgroundSessionData()

    async def set_message(self, key: str, context: BackgroundPickerContext) -> None:
        await self.load()
        async with self.lock:
            updated = self.data.model_copy(
                update={
                    "messages": {
                        **self.data.messages,
                        key: context.model_copy(deep=True),
                    }
                }
            )
            await self._save_locked(updated)
            self.data = updated

    async def get_message(self, key: str) -> BackgroundPickerContext | None:
        await self.load()
        context = self.data.messages.get(key)
        return context.model_copy(deep=True) if context else None

    async def _save_locked(self, data: BackgroundSessionData) -> None:
        await run_storage(self._write_atomic, data.model_dump_json(indent=2))

    def _write_atomic(self, payload: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
        )
        try:
            with temporary.open("w", encoding="utf-8") as file:
                file.write(payload)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
