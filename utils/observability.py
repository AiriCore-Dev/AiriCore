import asyncio
import threading
import time

from nonebot import logger as _logger
from nonebot.adapters.onebot.v11.exception import ActionFailed, NetworkError


def compact_api_timeout_traceback(record) -> bool:
    message = str(record.get("message", ""))
    if not message.startswith("Running Matcher(") or not message.endswith("failed."):
        return False
    exception = record.get("exception")
    value = getattr(exception, "value", None)
    if not isinstance(value, (ActionFailed, NetworkError)):
        return False
    text = f"{type(value).__name__} {value}".lower()
    if "timeout" not in text and "timed out" not in text and "超时" not in text:
        return False
    record["message"] = f"{message} {value}"
    record["exception"] = None
    return True


class PrefixedLogger:
    def __init__(self, name: str):
        self._name = name
        self._log = _logger.opt(depth=1)

    def _fmt(self, msg):
        return f"[{self._name}] {msg}"

    def debug(self, msg, *args, **kwargs):
        self._log.debug(self._fmt(msg))

    def info(self, msg, *args, **kwargs):
        self._log.info(self._fmt(msg))

    def warning(self, msg, *args, **kwargs):
        self._log.warning(self._fmt(msg))

    warn = warning

    def error(self, msg, *args, **kwargs):
        self._log.error(self._fmt(msg))

    def critical(self, msg, *args, **kwargs):
        self._log.critical(self._fmt(msg))

    def exception(self, msg, *args, **kwargs):
        _logger.opt(depth=1, exception=True).error(self._fmt(msg))

    def setLevel(self, level):
        return None

    def addHandler(self, handler):
        return None

    @property
    def handlers(self):
        return [None]


def get_logger(name: str) -> PrefixedLogger:
    return PrefixedLogger(name)


SAMPLE_INTERVAL = 60.0
REPORT_EVERY = 10
LAG_WARN_SECS = 1.0
TASK_WARN_COUNT = 200
_task = None


async def measure_lag(samples: int = 5, delay: float = 0.2) -> float:
    worst = 0.0
    for _ in range(samples):
        start = time.perf_counter()
        await asyncio.sleep(delay)
        worst = max(worst, time.perf_counter() - start - delay)
    return worst


def _process():
    try:
        import psutil
        return psutil.Process()
    except Exception:
        return None


def _fd_count(proc) -> int:
    if proc is None:
        return -1
    try:
        return proc.num_fds()
    except Exception:
        return -1


def _rss_mb(proc) -> float:
    if proc is None:
        return -1.0
    try:
        return proc.memory_info().rss / 1048576
    except Exception:
        return -1.0


def snapshot(proc, lag: float) -> str:
    return (f"运行状态：事件循环延迟 {lag * 1000:.0f}ms，协程 {len(asyncio.all_tasks())} 个，"
            f"线程 {threading.active_count()} 个，句柄 {_fd_count(proc)} 个，内存 {_rss_mb(proc):.0f}MB")


async def _monitor() -> None:
    proc = _process()
    round_no = 0
    while True:
        await asyncio.sleep(SAMPLE_INTERVAL)
        round_no += 1
        try:
            lag = await measure_lag()
            tasks = len(asyncio.all_tasks())
            line = snapshot(proc, lag)
            if lag >= LAG_WARN_SECS or tasks >= TASK_WARN_COUNT:
                _logger.warning(f"{line}；消息处理已开始积压，回复会明显变慢")
            elif round_no % REPORT_EVERY == 0:
                _logger.info(line)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _logger.warning(f"运行状态采样失败: {e}")


def start():
    global _task
    if _task is not None and not _task.done():
        return _task
    from utils.coordination import registry

    _task = registry.create(_monitor(), owner="observability", key="monitor")
    return _task


def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
