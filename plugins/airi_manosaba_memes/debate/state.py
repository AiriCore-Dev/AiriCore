import asyncio
import json
import os
import secrets
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ..runtime import logger, run_storage
from .parser import DebateRequest, validate_request


MAX_MESSAGES = 4096


class DebateSessionStore:
    def __init__(self, path: Path):
        self.path = path
        self.messages = {}
        self.lock = asyncio.Lock()
        self._loaded = False

    async def _load_locked(self):
        if not self._loaded:
            self.messages = await run_storage(self._load_sync)
            self._loaded = True

    def _load_sync(self):
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError("审问会话格式无效")
            messages = data["messages"]
            if not isinstance(messages, dict):
                raise ValueError("审问会话记录无效")
            restored = {}
            for key, item in list(messages.items())[-MAX_MESSAGES:]:
                if not isinstance(item, dict) or any(not isinstance(item.get(name), str) for name in ("sprite", "side", "text")):
                    raise ValueError("审问配方记录无效")
                restored[key] = validate_request(DebateRequest(**item))
            return restored
        except (ValueError, TypeError, KeyError):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = self.path.with_name(f"{self.path.name}.broken.{stamp}.{secrets.token_hex(4)}")
            os.replace(self.path, backup)
            logger.warning("审问会话数据损坏，已备份原文件并恢复空记录")
            return {}

    async def get_message(self, key: str) -> DebateRequest | None:
        async with self.lock:
            await self._load_locked()
            return self.messages.get(key)

    async def set_message(self, key: str, request: DebateRequest) -> None:
        validate_request(request)
        async with self.lock:
            await self._load_locked()
            updated = {name: value for name, value in self.messages.items() if name != key}
            updated[key] = request
            updated = dict(list(updated.items())[-MAX_MESSAGES:])
            payload = json.dumps({"schema_version": 1, "messages": {
                name: asdict(value) for name, value in updated.items()
            }}, ensure_ascii=False, indent=2)
            await run_storage(self._write_atomic, payload)
            self.messages = updated

    def _write_atomic(self, payload: str):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as file:
                file.write(payload + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
