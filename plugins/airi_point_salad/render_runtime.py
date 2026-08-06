import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor


_executor = None
_executor_lock = threading.Lock()
_slots = None
_slots_loop = None


def _get_executor():
    global _executor
    if _executor is not None:
        return _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="airi_point_salad",
            )
        return _executor


def _get_slots(loop):
    global _slots, _slots_loop
    if _slots is not None and _slots_loop is loop:
        return _slots
    with _executor_lock:
        if _slots is None or _slots_loop is not loop:
            _slots = asyncio.Semaphore(4)
            _slots_loop = loop
        return _slots


async def run_sync(function, *args):
    loop = asyncio.get_running_loop()
    slots = _get_slots(loop)
    await slots.acquire()
    try:
        future = _get_executor().submit(function, *args)
    except Exception:
        slots.release()
        raise

    def release_slot(_):
        try:
            loop.call_soon_threadsafe(slots.release)
        except RuntimeError:
            pass

    future.add_done_callback(release_slot)
    return await asyncio.wrap_future(future, loop=loop)


def shutdown():
    global _executor, _slots, _slots_loop
    with _executor_lock:
        executor = _executor
        _executor = None
        _slots = None
        _slots_loop = None
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)
