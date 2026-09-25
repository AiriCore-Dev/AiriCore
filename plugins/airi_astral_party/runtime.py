import asyncio
from functools import partial

from utils.coordination import registry
from utils.observability import get_logger

from .protocol import QueryError


_pending = set()
_render_lock = asyncio.Lock()
_closing = False
_maintenance_task = None
logger = get_logger('吉星派对')


def start_maintenance(maintain):
    global _maintenance_task
    if _maintenance_task is None or _maintenance_task.done():
        _maintenance_task = registry.create(_maintain(maintain), owner='airi_astral_party', key='飞魔会话更新')
    return _maintenance_task


async def _maintain(maintain):
    while not _closing:
        try:
            await maintain()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(f'飞魔会话自动更新未完成（{type(error).__name__}），请管理员私聊检查账号状态')
        await asyncio.sleep(3600)


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
    global _closing, _maintenance_task
    _closing = True
    if _maintenance_task is not None:
        _maintenance_task.cancel()
        await asyncio.gather(_maintenance_task, return_exceptions=True)
        _maintenance_task = None
    if _pending:
        await asyncio.gather(*tuple(_pending), return_exceptions=True)
