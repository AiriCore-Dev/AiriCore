import asyncio
from functools import partial

from utils.coordination import registry

from .protocol import QueryError


_pending = set()
_render_lock = asyncio.Lock()
_closing = False


async def run_sync(function, *args):
    async with _render_lock:
        future = asyncio.get_running_loop().run_in_executor(None, partial(function, *args))
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            await future
            raise


async def run_operation(coroutine):
    if _closing:
        coroutine.close()
        raise QueryError('吉星派对查询正在关闭，请稍后重试')
    task = registry.create(coroutine, owner='airi_astral_party', key='查询出图')
    _pending.add(task)
    task.add_done_callback(_pending.discard)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.shield(task)
        raise


async def shutdown():
    global _closing
    _closing = True
    if _pending:
        await asyncio.gather(*tuple(_pending), return_exceptions=True)
