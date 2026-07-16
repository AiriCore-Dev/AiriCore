
import copy
import pickle
import time
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from nonebot import logger
from nonebot.message import event_preprocessor
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


def _flush(force: bool = False) -> None:
    global _last_flush, _dirty
    now = time.time()
    if not force and (not _dirty or now - _last_flush < _FLUSH_INTERVAL):
        return
    try:
        _prune_old_days()
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STATS_FILE.with_suffix(".pk.tmp")
        with open(tmp, "wb") as f:
            pickle.dump(_stats, f)
        tmp.replace(_STATS_FILE)
        _last_flush = now
        _dirty = False
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>airi_switch 统计文件写入失败: {e}</y>")


def _bump(bot_id: str, direction: str, session: str) -> None:
    global _dirty
    with _lock:
        day = _stats.setdefault(_today(), {})
        bot = day.setdefault(str(bot_id), {"recv": {}, "sent": {}})
        bucket = bot.setdefault(direction, {})
        bucket[session] = bucket.get(session, 0) + 1
        _dirty = True
        _flush()


def get_stats(day: str = "") -> Dict[str, Any]:
    with _lock:
        return copy.deepcopy(_stats.get(day or _today(), {}))


def get_available_days() -> list:
    with _lock:
        return sorted(_stats.keys())


_load()


@event_preprocessor
def _count_recv(bot: Bot, event: MessageEvent):
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
