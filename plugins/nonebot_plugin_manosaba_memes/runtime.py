import asyncio
from functools import partial
from pathlib import Path

from utils.coordination import registry
from utils.observability import get_logger


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nonebot_plugin_manosaba_memes"
DATA_DIR.mkdir(parents=True, exist_ok=True)
logger = get_logger("魔裁表情包")
_render_lock = asyncio.Lock()
_pending = set()
_closing = False


async def _wait_worker(function, args, kwargs, lock, preserve_result=False):
    async with lock:
        future = asyncio.get_running_loop().run_in_executor(None, partial(function, *args, **kwargs))
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            result = await future
            if preserve_result:
                return result
            raise


async def run_sync(function, *args, **kwargs):
    if _closing:
        raise RuntimeError("魔裁表情包正在关闭，请稍后再试")
    task = registry.create(_wait_worker(function, args, kwargs, _render_lock), owner="nonebot_plugin_manosaba_memes", key=function.__name__)
    _pending.add(task)
    task.add_done_callback(_pending.discard)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.shield(task)
        raise


async def run_storage(function, *args):
    task = registry.create(_wait_worker(function, args, {}, asyncio.Lock(), True), owner="nonebot_plugin_manosaba_memes", key="会话存储")
    _pending.add(task)
    task.add_done_callback(_pending.discard)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        return await asyncio.shield(task)


async def shutdown() -> None:
    global _closing
    _closing = True
    while _pending:
        await asyncio.gather(*tuple(_pending), return_exceptions=True)
