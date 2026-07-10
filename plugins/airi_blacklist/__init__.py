from pathlib import Path
from typing import Literal
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from nonebot import get_driver, logger, on_fullmatch, on_startswith
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from nonebot.message import event_preprocessor, run_preprocessor
from nonebot.permission import SUPERUSER
from nonebot.exception import IgnoredException

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

block_stats = defaultdict(lambda: {"last_time": None, "count": 0})
stats_lock = asyncio.Lock()


def get_today_log_file() -> Path:
    return log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"


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
        log_file = get_today_log_file()
        lines = []
        for key, data in block_stats.items():
            if data["last_time"] and data["count"] > 0:
                lines.append(f"[{data['last_time']}] {key}，今日已尝试 {data['count']} 次\n")
        if lines:
            log_file.write_text("".join(lines), encoding="utf-8")


async def log_block_attempt(category: str, target_type: str, identifier: str, action: str):
    async with stats_lock:
        key = f"{category}{target_type} {identifier} {action}"
        block_stats[key]["last_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        block_stats[key]["count"] += 1


async def periodic_log_save():
    while True:
        await asyncio.sleep(1800)
        await save_block_log()


@driver.on_startup
async def startup():
    clean_old_logs()
    asyncio.create_task(periodic_log_save())


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
    file_path.write_text(json.dumps(namelist), encoding="utf-8")


def handle_user_namelist(
    event: MessageEvent,
    type: Literal["user_blacklist", "user_whitelist"],
    mode: Literal["add", "del"],
) -> str:
    msg = event.get_message()
    uids = [at.data["qq"] for at in msg["at"]]
    if mode == "add":
        namelist[type].extend(uids)
        _mode = "添加"
    elif mode == "del":
        namelist[type] = [uid for uid in namelist[type] if uid not in uids]
        _mode = "删除"
    save_namelist()
    _type = "黑名单" if "blacklist" in type else "白名单"
    return f"已{_mode} {len(uids)} 个用户{_type}: {', '.join(uids)}"


def handle_group_namelist(
    event: MessageEvent,
    type: Literal["group_blacklist", "group_whitelist"],
    mode: Literal["add", "del"],
) -> str:
    if isinstance(event, GroupMessageEvent):
        gids = [str(event.group_id)]
    else:
        msg = event.get_plaintext().strip()
        gids = [gid.strip() for gid in msg.split() if gid.strip().isdigit()]

    if mode == "add":
        namelist[type].extend(gids)
        _mode = "添加"
    elif mode == "del":
        namelist[type] = [gid for gid in namelist[type] if gid not in gids]
        _mode = "删除"
    save_namelist()
    _type = "黑名单" if "blacklist" in type else "白名单"
    return f"已{_mode} {len(gids)} 个群{_type}: {', '.join(gids)}"


def handle_bot_namelist(
    event: MessageEvent,
    type: Literal["bot_blacklist", "bot_whitelist"],
    mode: Literal["add", "del"],
) -> str:
    msg = event.get_plaintext().strip()
    bids = [bid.strip() for bid in msg.split() if bid.strip().isdigit()]

    if mode == "add":
        namelist[type].extend(bids)
        _mode = "添加"
    elif mode == "del":
        namelist[type] = [bid for bid in namelist[type] if bid not in bids]
        _mode = "删除"
    save_namelist()
    _type = "黑名单" if "blacklist" in type else "白名单"
    return f"已{_mode} {len(bids)} 个Bot{_type}: {', '.join(bids)}"


migrate_old_data()


@run_preprocessor
async def bot_namelist_processor(bot: Bot):
    bid = str(bot.self_id)
    if is_blacklist() and bid in namelist["bot_blacklist"]:
        await log_block_attempt("黑名单", "Bot", bid, "尝试连接")
        await bot.disconnect()
        return
    elif not (is_blacklist() or bid in namelist["bot_whitelist"]):
        await log_block_attempt("非白名单", "Bot", bid, "尝试连接")
        await bot.disconnect()
        return


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
        await log_block_attempt(category, target_type, identifier, "尝试使用Bot")
        raise IgnoredException("namelist block")


add_user_blacklist = on_startswith(("拉黑", "添加黑名单"), permission=SUPERUSER)


@add_user_blacklist.handle()
async def add_user_black_list(event: MessageEvent):
    msg = handle_user_namelist(event, "user_blacklist", "add")
    await add_user_blacklist.send(msg)


add_user_whitelist = on_startswith(("添加白名单"), permission=SUPERUSER)


@add_user_whitelist.handle()
async def add_user_white_list(event: MessageEvent):
    msg = handle_user_namelist(event, "user_whitelist", "add")
    await add_user_whitelist.send(msg)


del_user_blacklist = on_startswith(("删除黑名单", "解除黑名单"), permission=SUPERUSER)


@del_user_blacklist.handle()
async def del_user_black_list(event: MessageEvent):
    msg = handle_user_namelist(event, "user_blacklist", "del")
    await del_user_blacklist.send(msg)


del_user_whitelist = on_startswith(("删除白名单", "解除白名单"), permission=SUPERUSER)


@del_user_whitelist.handle()
async def del_user_white_list(event: MessageEvent):
    msg = handle_user_namelist(event, "user_whitelist", "del")
    await del_user_whitelist.send(msg)


add_group_blacklist = on_startswith(("拉黑群", "添加群黑名单"), permission=SUPERUSER)


@add_group_blacklist.handle()
async def add_group_black_list(event: MessageEvent):
    msg = handle_group_namelist(event, "group_blacklist", "add")
    await add_group_blacklist.send(msg)


add_group_whitelist = on_startswith(("添加群白名单"), permission=SUPERUSER)


@add_group_whitelist.handle()
async def add_group_white_list(event: MessageEvent):
    msg = handle_group_namelist(event, "group_whitelist", "add")
    await add_group_whitelist.send(msg)


del_group_blacklist = on_startswith(("删除群黑名单", "解除群黑名单"), permission=SUPERUSER)


@del_group_blacklist.handle()
async def del_group_black_list(event: MessageEvent):
    msg = handle_group_namelist(event, "group_blacklist", "del")
    await del_group_blacklist.send(msg)


del_group_whitelist = on_startswith(("删除群白名单", "解除群白名单"), permission=SUPERUSER)


@del_group_whitelist.handle()
async def del_group_white_list(event: MessageEvent):
    msg = handle_group_namelist(event, "group_whitelist", "del")
    await del_group_whitelist.send(msg)


add_bot_blacklist = on_startswith(("拉黑Bot", "添加Bot黑名单"), permission=SUPERUSER)


@add_bot_blacklist.handle()
async def add_bot_black_list(event: MessageEvent):
    msg = handle_bot_namelist(event, "bot_blacklist", "add")
    await add_bot_blacklist.send(msg)


add_bot_whitelist = on_startswith(("添加Bot白名单"), permission=SUPERUSER)


@add_bot_whitelist.handle()
async def add_bot_white_list(event: MessageEvent):
    msg = handle_bot_namelist(event, "bot_whitelist", "add")
    await add_bot_whitelist.send(msg)


del_bot_blacklist = on_startswith(("删除Bot黑名单", "解除Bot黑名单"), permission=SUPERUSER)


@del_bot_blacklist.handle()
async def del_bot_black_list(event: MessageEvent):
    msg = handle_bot_namelist(event, "bot_blacklist", "del")
    await del_bot_blacklist.send(msg)


del_bot_whitelist = on_startswith(("删除Bot白名单", "解除Bot白名单"), permission=SUPERUSER)


@del_bot_whitelist.handle()
async def del_bot_white_list(event: MessageEvent):
    msg = handle_bot_namelist(event, "bot_whitelist", "del")
    await del_bot_whitelist.send(msg)


check_user_blacklist = on_startswith(("查看黑名单", "查看黑名单用户"), permission=SUPERUSER)


@check_user_blacklist.handle()
async def check_user_black_list():
    await check_user_blacklist.send(f"当前用户黑名单: {', '.join(namelist['user_blacklist'])}")


check_user_whitelist = on_startswith(("查看白名单", "查看白名单用户"), permission=SUPERUSER)


@check_user_whitelist.handle()
async def check_user_white_list():
    await check_user_whitelist.send(f"当前用户白名单: {', '.join(namelist['user_whitelist'])}")


check_group_blacklist = on_startswith(("查看群黑名单"), permission=SUPERUSER)


@check_group_blacklist.handle()
async def check_group_black_list():
    await check_group_blacklist.send(f"当前群黑名单: {', '.join(namelist['group_blacklist'])}")


check_group_whitelist = on_startswith(("查看群白名单"), permission=SUPERUSER)


@check_group_whitelist.handle()
async def check_group_white_list():
    await check_group_whitelist.send(f"当前群白名单: {', '.join(namelist['group_whitelist'])}")


check_bot_blacklist = on_startswith(("查看Bot黑名单"), permission=SUPERUSER)


@check_bot_blacklist.handle()
async def check_bot_black_list():
    await check_bot_blacklist.send(f"当前Bot黑名单: {', '.join(namelist['bot_blacklist'])}")


check_bot_whitelist = on_startswith(("查看Bot白名单"), permission=SUPERUSER)


@check_bot_whitelist.handle()
async def check_bot_white_list():
    await check_bot_whitelist.send(f"当前Bot白名单: {', '.join(namelist['bot_whitelist'])}")


change_namelist = on_fullmatch(
    ("切换黑名单", "更改黑名单", "切换白名单", "更改白名单", "切换名单"), permission=SUPERUSER
)


@change_namelist.handle()
async def change_black_list():
    namelist["type"] = "whitelist" if is_blacklist() else "blacklist"
    save_namelist()
    await change_namelist.send(f'已切换为 {"黑名单" if is_blacklist() else "白名单"} 模式')
