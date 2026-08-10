import asyncio
import hashlib
import time
from collections import OrderedDict
from typing import Callable, Optional

import nonebot
from nonebot import logger
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor, run_preprocessor
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from . import counter

CLAIM_TTL = 15.0
CLAIM_MAX = 4096
DEFER_DELAY = 0.15
GROUPS_TTL = 2 * 3600
DECISIONS_KEY = "_airi_dedup_decisions"

_claims: "OrderedDict[str, dict]" = OrderedDict()
_deferrals: list[Callable[[str, str], bool]] = []
_bot_groups: dict = {}
_bot_groups_ts: dict = {}
_refresh_tasks: set = set()


def register_deferral(fn: Callable[[str, str], bool]) -> None:
    if fn not in _deferrals:
        _deferrals.append(fn)


def is_deferred(bot_id: str, plugin_name: str) -> bool:
    for fn in _deferrals:
        try:
            if fn(bot_id, plugin_name):
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


def note_group(bot_id: str, group_id) -> None:
    groups = _bot_groups.get(str(bot_id))
    if groups is not None:
        groups.add(str(group_id))


def in_group(bot_id: str, group_id) -> Optional[bool]:
    groups = _bot_groups.get(str(bot_id))
    if groups is None:
        return None
    return str(group_id) in groups


async def refresh_groups(bot) -> None:
    bot_id = str(bot.self_id)
    try:
        group_list = await bot.get_group_list()
        _bot_groups[bot_id] = {
            str(g["group_id"]) for g in group_list if g.get("group_id") is not None
        }
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>多bot去重群列表获取失败({bot_id}): {e}</y>")


def _spawn_refresh(bot) -> None:
    task = asyncio.ensure_future(refresh_groups(bot))
    _refresh_tasks.add(task)
    task.add_done_callback(_refresh_tasks.discard)


def _refresh_stale_groups(bots: dict) -> None:
    now = time.monotonic()
    for bot_id, bot in bots.items():
        bot_id = str(bot_id)
        if now - _bot_groups_ts.get(bot_id, 0.0) < GROUPS_TTL:
            continue
        _bot_groups_ts[bot_id] = now
        _spawn_refresh(bot)
    for bot_id in [b for b in _bot_groups_ts if b not in bots]:
        _bot_groups_ts.pop(bot_id, None)
        _bot_groups.pop(bot_id, None)


def directed_target(
    event: GroupMessageEvent, online_ids: set, bot_id: Optional[str] = None
) -> Optional[str]:
    candidates = []
    for seg in event.original_message:
        if seg.type == "at":
            qq = str(seg.data.get("qq", ""))
            if qq in online_ids and qq not in candidates:
                candidates.append(qq)
    reply = getattr(event, "reply", None)
    if reply is not None and getattr(reply.sender, "user_id", None) is not None:
        rid = str(reply.sender.user_id)
        if rid in online_ids and rid not in candidates:
            candidates.append(rid)
    for qq in candidates:
        if bot_id is not None and qq == str(bot_id):
            return qq
        if in_group(qq, event.group_id) is False:
            continue
        return qq
    return None


def _purge(now: float) -> None:
    stale = [k for k, v in _claims.items() if now - v["ts"] > CLAIM_TTL]
    for k in stale:
        _claims.pop(k, None)
    while len(_claims) > CLAIM_MAX:
        _claims.popitem(last=False)


def claim(bot_id: str, event: GroupMessageEvent, online_ids: set, scope: str = ""):
    now = time.monotonic()
    _purge(now)
    fp = f"{fingerprint(event)}:{scope}"
    directed = directed_target(event, online_ids, bot_id)
    entry = _claims.get(fp)
    new_round = (
        entry is None
        or bot_id in entry["seen"]
        or (directed is not None and entry["owner"] != directed)
    )
    if new_round:
        owner = directed or bot_id
        _claims[fp] = {"owner": owner, "seen": {bot_id}, "ts": now}
        _claims.move_to_end(fp)
        return owner == bot_id, owner, fp
    entry["seen"].add(bot_id)
    entry["ts"] = now
    _claims.move_to_end(fp)
    return entry["owner"] == bot_id, entry["owner"], fp


@event_preprocessor
async def _dedup_prepare(bot: Bot, event: MessageEvent, state: T_State):
    counter.count_recv(bot, event)
    if not isinstance(event, GroupMessageEvent):
        return
    bot_id = str(bot.self_id)
    note_group(bot_id, event.group_id)
    bots = nonebot.get_bots()
    _refresh_stale_groups(bots)
    state.setdefault(DECISIONS_KEY, {})


def _matcher_scope(matcher: Matcher) -> str:
    if matcher.plugin_id:
        return matcher.plugin_id
    source = getattr(matcher, "_source", None)
    module_name = matcher.module_name or ""
    lineno = getattr(source, "lineno", None)
    return f"{module_name}:{lineno}"


@run_preprocessor
async def _dedup(matcher: Matcher, bot: Bot, event: MessageEvent, state: T_State):
    if not isinstance(event, GroupMessageEvent):
        return
    bot_id = str(bot.self_id)
    plugin_name = matcher.plugin_name or ""
    scope = _matcher_scope(matcher)
    decisions = state.setdefault(DECISIONS_KEY, {})
    decision = decisions.get(scope)
    if decision is None and is_deferred(bot_id, plugin_name):
        await asyncio.sleep(DEFER_DELAY)
        decision = decisions.get(scope)
    if decision is None:
        bots = nonebot.get_bots()
        try:
            allowed, owner, fp = claim(bot_id, event, set(bots), scope)
        except Exception as e:
            logger.opt(colors=True).warning(
                f"<y>多bot去重判定异常，本条放行: {e}</y>"
            )
            decisions[scope] = (True, bot_id, "")
            return
        decision = decisions[scope] = (allowed, owner, fp)
    allowed, owner, fp = decision
    if allowed:
        return
    logger.opt(colors=True).debug(
        f"<y>多bot去重: 插件{plugin_name or scope} 群{event.group_id} "
        f"指纹{fp[:8]} 归属{owner}, 丢弃 {bot_id}</y>"
    )
    raise IgnoredException("multi-bot dedup")


@nonebot.get_driver().on_bot_connect
async def _refresh_on_connect(bot: Bot):
    _bot_groups_ts[str(bot.self_id)] = time.monotonic()
    await refresh_groups(bot)


@nonebot.get_driver().on_bot_disconnect
async def _forget_on_disconnect(bot: Bot):
    bot_id = str(bot.self_id)
    _bot_groups.pop(bot_id, None)
    _bot_groups_ts.pop(bot_id, None)
