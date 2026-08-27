import asyncio
from dataclasses import dataclass
from typing import Any

from utils.observability import get_logger

logger = get_logger("coordination")


@dataclass(frozen=True)
class TaskInfo:
    owner: str
    key: Any = None


class TaskRegistry:

    def __init__(self):
        self._tasks = {}

    def create(self, coro, *, owner, key=None) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks[task] = TaskInfo(owner=owner, key=key)
        task.add_done_callback(self._on_done)
        return task

    def _on_done(self, task: asyncio.Task) -> None:
        info = self._tasks.pop(task, None)
        if info is None:
            return
        if task.cancelled():
            return
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            logger.exception(f"后台任务异常: owner={info.owner} key={info.key} error={exc}")

    async def cancel_all(self) -> None:
        pending = tuple(self._tasks)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def snapshot(self) -> tuple[TaskInfo, ...]:
        return tuple(self._tasks.values())


registry = TaskRegistry()
