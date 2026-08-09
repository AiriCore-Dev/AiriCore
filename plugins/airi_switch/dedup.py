import asyncio
import hashlib
import time
from collections import OrderedDict
from typing import Callable, Optional

import nonebot
from nonebot import logger
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from . import counter

CLAIM_TTL = 120.0
CLAIM_MAX = 4096
DEFER_DELAY = 0.15

_claims: "OrderedDict[str, dict]" = OrderedDict()
_deferrals: list = []


def register_deferral(fn: Callable[[str], bool]) -> None:
    if fn not in _deferrals:
        _deferrals.append(fn)


def is_deferred(bot_id: str) -> bool:
    for fn in _deferrals:
        try:
            if fn(bot_id):
                return True
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>多bot去重降级判定失败: {e}</y>")
    return False


def fingerprint(event: GroupMessageEvent) -> str:
    texts = []
    counts = {}
    for seg in event.original_message:
        if seg.type == "text":
            texts.append(str(seg.data.get("text", "")))
        elif seg.type not in ("at", "reply"):
            counts[seg.type] = counts.get(seg.type, 0) + 1
    text = "".join(texts).strip()
    types = ",".join(f"{k}:{counts[k]}" for k in sorted(counts))
    raw = f"{event.group_id}|{event.user_id}|{text}|{types}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def directed_target(event: GroupMessageEvent, online_ids: set) -> Optional[str]:
    for seg in event.original_message:
        if seg.type == "at":
            qq = str(seg.data.get("qq", ""))
            if qq in online_ids:
                return qq
    reply = getattr(event, "reply", None)
    if reply is not None and getattr(reply.sender, "user_id", None) is not None:
        rid = str(reply.sender.user_id)
        if rid in online_ids:
            return rid
    return None


def _purge(now: float) -> None:
    stale = [k for k, v in _claims.items() if now - v["ts"] > CLAIM_TTL]
    for k in stale:
        _claims.pop(k, None)
    while len(_claims) > CLAIM_MAX:
        _claims.popitem(last=False)


def claim(bot_id: str, event: GroupMessageEvent, online_ids: set):
    now = time.monotonic()
    _purge(now)
    fp = fingerprint(event)
    entry = _claims.get(fp)
    if entry is None or bot_id in entry["seen"]:
        owner = directed_target(event, online_ids) or bot_id
        _claims[fp] = {"owner": owner, "seen": {bot_id}, "ts": now}
        _claims.move_to_end(fp)
        return owner == bot_id, owner, fp
    entry["seen"].add(bot_id)
    entry["ts"] = now
    _claims.move_to_end(fp)
    return entry["owner"] == bot_id, entry["owner"], fp


@event_preprocessor
async def _dedup(bot: Bot, event: MessageEvent):
    counter.count_recv(bot, event)
    if not isinstance(event, GroupMessageEvent):
        return
    bot_id = str(bot.self_id)
    if is_deferred(bot_id):
        await asyncio.sleep(DEFER_DELAY)
    allowed, owner, fp = claim(bot_id, event, set(nonebot.get_bots()))
    if allowed:
        return
    logger.opt(colors=True).debug(
        f"<y>多bot去重: 群{event.group_id} 指纹{fp[:8]} 归属{owner}, 丢弃 {bot_id}</y>"
    )
    raise IgnoredException("multi-bot dedup")
