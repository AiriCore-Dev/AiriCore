import os
import re
import tempfile
import time
from pathlib import Path
from typing import Literal
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict
import asyncio
from nonebot import get_driver, logger, on_fullmatch, on_startswith
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from utils.superuser_2fa import SUPERUSER_2FA

try:
    import ujson as json
except ModuleNotFoundError:
    import json

driver = get_driver()
superusers = driver.config.superusers

base_path = Path(__file__).parent
file_path = base_path / "namelist.json"
log_dir = base_path / "log"
log_dir.mkdir(exist_ok=True)

namelist = (
    json.loads(file_path.read_text("utf-8"))
    if file_path.is_file()
    else {
        "type": "blacklist",
        "user_blacklist": [],
        "user_whitelist": [],
        "group_blacklist": [],
        "group_whitelist": [],
        "bot_blacklist": [],
        "bot_whitelist": [],
    }
)

block_stats = defaultdict(lambda: defaultdict(lambda: {"last_time": None, "count": 0}))
stats_lock = asyncio.Lock()
_bg_tasks = set()
LOG_LINE_RE = re.compile(r"^\[(.+?)\] (.+)，今日已尝试 (\d+) 次$")

LOG_DEDUP_TTL = 15.0
LOG_DEDUP_MAX = 4096
_logged_rounds: "OrderedDict[str, dict]" = OrderedDict()


def _event_fingerprint(event) -> str | None:
    if isinstance(event, GroupMessageEvent):
        try:
            from plugins.airi_switch import dedup
        except Exception:
            return None
        try:
            return dedup.fingerprint(event)
        except Exception:
            return None
    if isinstance(event, MessageEvent) or event is None:
        return None
    parts = [
        getattr(event, "post_type", ""),
        getattr(event, "notice_type", ""),
        getattr(event, "request_type", ""),
        getattr(event, "sub_type", ""),
        getattr(event, "user_id", ""),
        getattr(event, "group_id", ""),
        getattr(event, "operator_id", ""),
    ]
    return "notice|" + "|".join(str(part) for part in parts)


def _first_log_of_round(bot_id: str, key: str, event) -> bool:
    fingerprint = _event_fingerprint(event)
    if fingerprint is None:
        return True
    now = time.monotonic()
    for stale in [k for k, v in _logged_rounds.items() if now - v["ts"] > LOG_DEDUP_TTL]:
        _logged_rounds.pop(stale, None)
    while len(_logged_rounds) > LOG_DEDUP_MAX:
        _logged_rounds.popitem(last=False)
    token = f"{fingerprint}|{key}"
    entry = _logged_rounds.get(token)
    if entry is None or bot_id in entry["seen"]:
        _logged_rounds[token] = {"seen": {bot_id}, "ts": now}
        _logged_rounds.move_to_end(token)
        return True
    entry["seen"].add(bot_id)
    entry["ts"] = now
    _logged_rounds.move_to_end(token)
    return False


def get_today_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_log_file(date: str) -> Path:
    return log_dir / f"{date}.log"


def load_existing_stats() -> None:
    for log_file in log_dir.glob("*.log"):
        date = log_file.stem
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            continue
        try:
            content = log_file.read_text("utf-8")
        except OSError:
            continue
        for line in content.splitlines():
            m = LOG_LINE_RE.match(line.strip())
            if not m:
                continue
            block_stats[date][m.group(2)] = {
                "last_time": m.group(1),
                "count": int(m.group(3)),
            }


def clean_old_logs():
    cutoff = datetime.now() - timedelta(days=7)
    for log_file in log_dir.glob("*.log"):
        try:
            file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
            if file_date < cutoff:
                log_file.unlink()
                logger.debug(f"已删除过期日志: {log_file.name}")
        except ValueError:
            pass


async def save_block_log():
    async with stats_lock:
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        for stale in [d for d in block_stats if d < cutoff]:
            del block_stats[stale]
        for date, entries in block_stats.items():
            lines = [
                f"[{data['last_time']}] {key}，今日已尝试 {data['count']} 次\n"
                for key, data in entries.items()
                if data["last_time"] and data["count"] > 0
            ]
            if not lines:
                continue
            try:
                get_log_file(date).write_text("".join(lines), encoding="utf-8")
            except OSError as e:
                logger.warning(f"拦截统计落盘失败: {e}")


async def log_block_attempt(category: str, target_type: str, identifier: str, action: str,
                            bot=None, event=None):
    key = f"{category}{target_type} {identifier} {action}"
    if bot is not None and event is not None:
        if not _first_log_of_round(str(bot.self_id), key, event):
            return
    async with stats_lock:
        today = get_today_date()
        block_stats[today][key]["last_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        block_stats[today][key]["count"] += 1


async def periodic_log_save():
    while True:
        await asyncio.sleep(1800)
        try:
            await save_block_log()
            clean_old_logs()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"拦截统计定时任务异常: {e}")


@driver.on_startup
async def startup():
    clean_old_logs()
    load_existing_stats()
    task = asyncio.create_task(periodic_log_save())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


@driver.on_shutdown
async def shutdown():
    await save_block_log()


def migrate_old_data():
    if "blacklist" in namelist and "user_blacklist" not in namelist:
        namelist["user_blacklist"] = namelist.pop("blacklist", [])
        namelist["user_whitelist"] = namelist.pop("whitelist", [])
        namelist["group_blacklist"] = []
        namelist["group_whitelist"] = []
        namelist["bot_blacklist"] = []
        namelist["bot_whitelist"] = []
        save_namelist()
        logger.info("已迁移旧版黑白名单数据")


def is_blacklist() -> bool:
    return namelist["type"] == "blacklist"


def save_namelist() -> None:
    data = json.dumps(namelist)
    fd, tmp = tempfile.mkstemp(dir=str(base_path), prefix=".namelist-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, file_path)
    except Exception as e:
        logger.error(f"名单落盘失败: {e}")
        try:
            os.unlink(tmp)
        except OSError:
            pass


def handle_user_namelist(
    event: MessageEvent,
    type: Literal["user_blacklist", "user_whitelist"],
    mode: Literal["add", "del"],
) -> str:
    msg = event.get_message()
    uids = [str(at.data["qq"]) for at in msg["at"]]
    _type = "黑名单" if "blacklist" in type else "白名单"
    if not uids:
        return f"请 @ 需要操作的用户后再发送该指令。"
    other = type.replace("blacklist", "TMP").replace("whitelist", "blacklist").replace("TMP", "whitelist")
    if mode == "add":
        conflict = [u for u in uids if u in namelist.get(other, [])]
        if conflict:
            return f"以下用户已在对立名单中，请先移除: {', '.join(conflict)}"
        added = [u for u in uids if u not in namelist[type]]
        namelist[type].extend(added)
        save_namelist()
        return f"已添加 {len(added)} 个用户{_type}: {', '.join(added) or '无'}"
    namelist[type] = [uid for uid in namelist[type] if uid not in uids]
    save_namelist()
    return f"已删除 {len(uids)} 个用户{_type}: {', '.join(uids)}"


def handle_group_namelist(
    event: MessageEvent,
    type: Literal["group_blacklist", "group_whitelist"],
    mode: Literal["add", "del"],
) -> str:
    msg = event.get_plaintext().strip()
    gids = [gid.strip() for gid in msg.split() if gid.strip().isdigit()]
    if not gids and isinstance(event, GroupMessageEvent):
        gids = [str(event.group_id)]

    _type = "黑名单" if "blacklist" in type else "白名单"
    if not gids:
        return "请在指令后附上群号，或在目标群内直接发送该指令。"
    other = type.replace("blacklist", "TMP").replace("whitelist", "blacklist").replace("TMP", "whitelist")
    if mode == "add":
        conflict = [g for g in gids if g in namelist.get(other, [])]
        if conflict:
            return f"以下群已在对立名单中，请先移除: {', '.join(conflict)}"
        added = [g for g in gids if g not in namelist[type]]
        namelist[type].extend(added)
        save_namelist()
        return f"已添加 {len(added)} 个群{_type}: {', '.join(added) or '无'}"
    namelist[type] = [gid for gid in namelist[type] if gid not in gids]
    save_namelist()
    return f"已删除 {len(gids)} 个群{_type}: {', '.join(gids)}"


def handle_bot_namelist(
    event: MessageEvent,
    type: Literal["bot_blacklist", "bot_whitelist"],
    mode: Literal["add", "del"],
) -> str:
    msg = event.get_plaintext().strip()
    bids = [bid.strip() for bid in msg.split() if bid.strip().isdigit()]

    _type = "黑名单" if "blacklist" in type else "白名单"
    if not bids:
        return "请在指令后附上 Bot 的 QQ 号。"
    other = type.replace("blacklist", "TMP").replace("whitelist", "blacklist").replace("TMP", "whitelist")
    if mode == "add":
        conflict = [b for b in bids if b in namelist.get(other, [])]
        if conflict:
            return f"以下 Bot 已在对立名单中，请先移除: {', '.join(conflict)}"
        added = [b for b in bids if b not in namelist[type]]
        namelist[type].extend(added)
        save_namelist()
        return f"已添加 {len(added)} 个Bot{_type}: {', '.join(added) or '无'}"
    namelist[type] = [bid for bid in namelist[type] if bid not in bids]
    save_namelist()
    return f"已删除 {len(bids)} 个Bot{_type}: {', '.join(bids)}"


migrate_old_data()


@driver.on_bot_connect
async def bot_namelist_processor(bot: Bot):
    bid = str(bot.self_id)
    if is_blacklist():
        if bid in namelist["bot_blacklist"]:
            await log_block_attempt("黑名单", "Bot", bid, "尝试连接")
            await bot.disconnect()
        return
    if not namelist["bot_whitelist"]:
        logger.warning("当前为白名单模式但 Bot 白名单为空，已放行所有 Bot 连接以避免自锁")
        return
    if bid not in namelist["bot_whitelist"]:
        await log_block_attempt("非白名单", "Bot", bid, "尝试连接")
        await bot.disconnect()


@event_preprocessor
async def notice_namelist_processor(bot: Bot, event: Event):
    if isinstance(event, MessageEvent):
        return
    uid = getattr(event, "user_id", None)
    if uid is None:
        return
    uid = str(uid)
    if uid in superusers:
        return
    gid = getattr(event, "group_id", None)
    gid = str(gid) if gid is not None else None

    if is_blacklist():
        if uid in namelist["user_blacklist"]:
            await log_block_attempt("黑名单", "用户", uid, "尝试触发通知事件", bot, event)
            raise IgnoredException("namelist block")
        if gid and gid in namelist["group_blacklist"]:
            await log_block_attempt("黑名单", "群聊", gid, "尝试触发通知事件", bot, event)
            raise IgnoredException("namelist block")
        return
    if uid not in namelist["user_whitelist"]:
        await log_block_attempt("非白名单", "用户", uid, "尝试触发通知事件", bot, event)
        raise IgnoredException("namelist block")
    if gid and gid not in namelist["group_whitelist"]:
        await log_block_attempt("非白名单", "群聊", gid, "尝试触发通知事件", bot, event)
        raise IgnoredException("namelist block")


@event_preprocessor
async def namelist_processor(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)
    if uid in superusers:
        return

    should_block = False
    category = ""
    target_type = ""
    identifier = ""

    if is_blacklist():
        if uid in namelist["user_blacklist"]:
            should_block = True
            category = "黑名单"
            target_type = "用户"
            identifier = uid
        elif isinstance(event, GroupMessageEvent):
            gid = str(event.group_id)
            if gid in namelist["group_blacklist"]:
                should_block = True
                category = "黑名单"
                target_type = "群聊"
                identifier = gid
    else:
        if uid not in namelist["user_whitelist"]:
            should_block = True
            category = "非白名单"
            target_type = "用户"
            identifier = uid
        elif isinstance(event, GroupMessageEvent):
            gid = str(event.group_id)
            if gid not in namelist["group_whitelist"]:
                should_block = True
                category = "非白名单"
                target_type = "群聊"
                identifier = gid

    if should_block:
        await log_block_attempt(category, target_type, identifier, "尝试使用Bot", bot, event)
        raise IgnoredException("namelist block")


def _not_prefixed_by(*prefixes):
    async def _rule(event: MessageEvent) -> bool:
        text = event.get_plaintext().strip()
        low = text.lower()
        return not any(low.startswith(p.lower()) for p in prefixes)

    return _rule


add_user_blacklist = on_startswith(
    ("拉黑", "添加黑名单"),
    permission=SUPERUSER_2FA,
    priority=5,
    rule=_not_prefixed_by("拉黑群", "拉黑Bot"),
)


@add_user_blacklist.handle()
async def add_user_black_list(event: MessageEvent):
    msg = handle_user_namelist(event, "user_blacklist", "add")
    await add_user_blacklist.send(msg)


add_user_whitelist = on_startswith(("添加白名单",), permission=SUPERUSER_2FA, priority=5)


@add_user_whitelist.handle()
async def add_user_white_list(event: MessageEvent):
    msg = handle_user_namelist(event, "user_whitelist", "add")
    await add_user_whitelist.send(msg)


del_user_blacklist = on_startswith(("删除黑名单", "解除黑名单"), permission=SUPERUSER_2FA, priority=5)


@del_user_blacklist.handle()
async def del_user_black_list(event: MessageEvent):
    msg = handle_user_namelist(event, "user_blacklist", "del")
    await del_user_blacklist.send(msg)


del_user_whitelist = on_startswith(("删除白名单", "解除白名单"), permission=SUPERUSER_2FA, priority=5)


@del_user_whitelist.handle()
async def del_user_white_list(event: MessageEvent):
    msg = handle_user_namelist(event, "user_whitelist", "del")
    await del_user_whitelist.send(msg)


add_group_blacklist = on_startswith(("拉黑群", "添加群黑名单"), permission=SUPERUSER_2FA, priority=1)


@add_group_blacklist.handle()
async def add_group_black_list(event: MessageEvent):
    msg = handle_group_namelist(event, "group_blacklist", "add")
    await add_group_blacklist.send(msg)


add_group_whitelist = on_startswith(("添加群白名单",), permission=SUPERUSER_2FA, priority=1)


@add_group_whitelist.handle()
async def add_group_white_list(event: MessageEvent):
    msg = handle_group_namelist(event, "group_whitelist", "add")
    await add_group_whitelist.send(msg)


del_group_blacklist = on_startswith(("删除群黑名单", "解除群黑名单"), permission=SUPERUSER_2FA, priority=1)


@del_group_blacklist.handle()
async def del_group_black_list(event: MessageEvent):
    msg = handle_group_namelist(event, "group_blacklist", "del")
    await del_group_blacklist.send(msg)


del_group_whitelist = on_startswith(("删除群白名单", "解除群白名单"), permission=SUPERUSER_2FA, priority=1)


@del_group_whitelist.handle()
async def del_group_white_list(event: MessageEvent):
    msg = handle_group_namelist(event, "group_whitelist", "del")
    await del_group_whitelist.send(msg)


add_bot_blacklist = on_startswith(("拉黑Bot", "添加Bot黑名单"), permission=SUPERUSER_2FA, priority=1, ignorecase=True)


@add_bot_blacklist.handle()
async def add_bot_black_list(event: MessageEvent):
    msg = handle_bot_namelist(event, "bot_blacklist", "add")
    await add_bot_blacklist.send(msg)


add_bot_whitelist = on_startswith(("添加Bot白名单",), permission=SUPERUSER_2FA, priority=1)


@add_bot_whitelist.handle()
async def add_bot_white_list(event: MessageEvent):
    msg = handle_bot_namelist(event, "bot_whitelist", "add")
    await add_bot_whitelist.send(msg)


del_bot_blacklist = on_startswith(("删除Bot黑名单", "解除Bot黑名单"), permission=SUPERUSER_2FA, priority=1, ignorecase=True)


@del_bot_blacklist.handle()
async def del_bot_black_list(event: MessageEvent):
    msg = handle_bot_namelist(event, "bot_blacklist", "del")
    await del_bot_blacklist.send(msg)


del_bot_whitelist = on_startswith(("删除Bot白名单", "解除Bot白名单"), permission=SUPERUSER_2FA, priority=1, ignorecase=True)


@del_bot_whitelist.handle()
async def del_bot_white_list(event: MessageEvent):
    msg = handle_bot_namelist(event, "bot_whitelist", "del")
    await del_bot_whitelist.send(msg)


check_user_blacklist = on_startswith(("查看黑名单", "查看黑名单用户"), permission=SUPERUSER_2FA, priority=5)


@check_user_blacklist.handle()
async def check_user_black_list():
    await check_user_blacklist.send(f"当前用户黑名单: {', '.join(namelist['user_blacklist'])}")


check_user_whitelist = on_startswith(("查看白名单", "查看白名单用户"), permission=SUPERUSER_2FA, priority=5)


@check_user_whitelist.handle()
async def check_user_white_list():
    await check_user_whitelist.send(f"当前用户白名单: {', '.join(namelist['user_whitelist'])}")


check_group_blacklist = on_startswith(("查看群黑名单",), permission=SUPERUSER_2FA, priority=1)


@check_group_blacklist.handle()
async def check_group_black_list():
    await check_group_blacklist.send(f"当前群黑名单: {', '.join(namelist['group_blacklist'])}")


check_group_whitelist = on_startswith(("查看群白名单",), permission=SUPERUSER_2FA, priority=1)


@check_group_whitelist.handle()
async def check_group_white_list():
    await check_group_whitelist.send(f"当前群白名单: {', '.join(namelist['group_whitelist'])}")


check_bot_blacklist = on_startswith(("查看Bot黑名单",), permission=SUPERUSER_2FA, priority=1)


@check_bot_blacklist.handle()
async def check_bot_black_list():
    await check_bot_blacklist.send(f"当前Bot黑名单: {', '.join(namelist['bot_blacklist'])}")


check_bot_whitelist = on_startswith(("查看Bot白名单",), permission=SUPERUSER_2FA, priority=1)


@check_bot_whitelist.handle()
async def check_bot_white_list():
    await check_bot_whitelist.send(f"当前Bot白名单: {', '.join(namelist['bot_whitelist'])}")


change_namelist = on_fullmatch(
    ("切换黑名单", "更改黑名单", "切换白名单", "更改白名单", "切换名单"), permission=SUPERUSER_2FA
)


@change_namelist.handle()
async def change_black_list():
    if is_blacklist():
        if not namelist["bot_whitelist"]:
            await change_namelist.finish(
                "切换到白名单模式前请先用「添加Bot白名单 <QQ号>」配置至少一个 Bot，"
                "否则切换后全部 Bot 会立刻掉线且无法用指令恢复。"
            )
        if not namelist["user_whitelist"]:
            await change_namelist.finish(
                "切换到白名单模式前请先用「添加白名单 @用户」配置至少一个用户，"
                "否则除 superuser 外没人能使用 Bot。"
            )
    namelist["type"] = "whitelist" if is_blacklist() else "blacklist"
    save_namelist()
    await change_namelist.send(f'已切换为 {"黑名单" if is_blacklist() else "白名单"} 模式')
