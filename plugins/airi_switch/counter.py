
import pickle
import time
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

UTC_PLUS_8 = timezone(timedelta(hours=8))

_SEND_APIS = {
    "send_msg": None,
    "send_group_msg": "group_id",
    "send_private_msg": None,
    "send_group_forward_msg": "group_id",
    "send_private_forward_msg": None,
    "send_forward_msg": None,
}

PRIVATE_KEY = "private"

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "airi_switch"
_STATS_FILE = _DATA_DIR / "msg_stats.pk"

_FLUSH_INTERVAL = 15.0
_RETENTION_DAYS = 90

_lock = threading.Lock()
_stats: Dict[str, Any] = {}
_last_flush = 0.0
_dirty = False


def _today() -> str:
    return datetime.now(UTC_PLUS_8).strftime("%Y-%m-%d")


def _prune_old_days() -> int:
    cutoff = (datetime.now(UTC_PLUS_8) - timedelta(days=_RETENTION_DAYS)).strftime("%Y-%m-%d")
    stale = [day for day in _stats if day < cutoff]
    for day in stale:
        _stats.pop(day, None)
    return len(stale)


def _load() -> None:
    global _stats
    if _STATS_FILE.is_file():
        try:
            with open(_STATS_FILE, "rb") as f:
                _stats = pickle.load(f)
            _prune_old_days()
            return
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>airi_switch 统计文件读取失败,已重置: {e}</y>")
    _stats = {}


def _copy_day(day_stats: Dict[str, Any]) -> Dict[str, Any]:
    return {
        bot_id: {
            direction: dict(bucket)
            for direction, bucket in directions.items()
        }
        for bot_id, directions in day_stats.items()
    }


def _snapshot() -> Dict[str, Any]:
    return {day: _copy_day(day_stats) for day, day_stats in _stats.items()}


def _flush(force: bool = False) -> None:
    global _last_flush, _dirty
    now = time.time()
    with _lock:
        if not force and (not _dirty or now - _last_flush < _FLUSH_INTERVAL):
            return
        _prune_old_days()
        snapshot = _snapshot()
        _last_flush = now
        _dirty = False
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STATS_FILE.with_suffix(".pk.tmp")
        with open(tmp, "wb") as f:
            pickle.dump(snapshot, f)
        tmp.replace(_STATS_FILE)
    except Exception as e:
        with _lock:
            _dirty = True
        logger.opt(colors=True).warning(f"<y>airi_switch 统计文件写入失败: {e}</y>")


def flush() -> None:
    _flush(force=True)


def _writer_loop() -> None:
    while True:
        time.sleep(_FLUSH_INTERVAL)
        try:
            _flush()
        except Exception:
            continue


_writer_thread = threading.Thread(target=_writer_loop, daemon=True, name="airi_switch_counter")


def _bump(bot_id: str, direction: str, session: str) -> None:
    global _dirty
    with _lock:
        day = _stats.setdefault(_today(), {})
        bot = day.setdefault(str(bot_id), {"recv": {}, "sent": {}})
        bucket = bot.setdefault(direction, {})
        bucket[session] = bucket.get(session, 0) + 1
        _dirty = True


def get_stats(day: str = "") -> Dict[str, Any]:
    with _lock:
        return _copy_day(_stats.get(day or _today(), {}))


def get_available_days() -> list:
    with _lock:
        return sorted(_stats.keys())


def preload(max_bytes: int = 0):
    with _lock:
        if not _stats:
            _load()
        return len(_stats), 0


_load()
_writer_thread.start()

try:
    from nonebot import get_driver as _get_driver

    @_get_driver().on_shutdown
    async def _flush_on_shutdown():
        _flush(force=True)
except Exception:
    pass


def count_recv(bot: Bot, event: MessageEvent) -> None:
    session = str(event.group_id) if isinstance(event, GroupMessageEvent) else PRIVATE_KEY
    _bump(bot.self_id, "recv", session)


@Bot.on_called_api
async def _count_sent(bot, exception, api: str, data: Dict[str, Any], result):
    if exception is not None or api not in _SEND_APIS:
        return
    field = _SEND_APIS[api]
    if field is not None and data.get(field) is not None:
        session = str(data[field])
    elif data.get("group_id") is not None:
        session = str(data["group_id"])
    elif data.get("user_id") is not None:
        session = PRIVATE_KEY
    else:
        session = PRIVATE_KEY
    _bump(bot.self_id, "sent", session)
