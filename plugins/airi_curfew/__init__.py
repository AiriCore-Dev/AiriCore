import datetime
from collections import defaultdict
from nonebot import get_driver, logger
from nonebot.message import run_preprocessor
from nonebot.matcher import Matcher
from nonebot.exception import IgnoredException
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent

driver = get_driver()
config = driver.config

ALWAYS_ALLOWED_PLUGINS = {"airi_switch", "airi_blacklist"}

CURFEW_BOT_IDS: set[str] = set()
CURFEW_PLUGIN_WHITELIST: set[str] = set(ALWAYS_ALLOWED_PLUGINS)
notified_groups: dict[str, set[str]] = defaultdict(set)

CURFEW_MESSAGES = [
    "慢慢长夜，该睡觉啦~（哈啊）\n祝你做一个美好的梦！\n明天早上6点之后再来找我吧！晚安！",
    "Zzz......\n（airi似乎正在睡觉）\n旁边有一张字条：\n熬夜伤身体，请一定要早睡！\n闹钟上的定时：6:00 AM",
]


def _load_curfew_config():
    global CURFEW_BOT_IDS, CURFEW_PLUGIN_WHITELIST
    bot_ids = getattr(config, "curfew_bot_ids", [])
    CURFEW_BOT_IDS = set(str(bid) for bid in bot_ids)
    whitelist = getattr(config, "curfew_plugin_whitelist", [])
    CURFEW_PLUGIN_WHITELIST = set(whitelist) | set(ALWAYS_ALLOWED_PLUGINS)


_load_curfew_config()


def is_curfew_time() -> bool:
    hour = datetime.datetime.now().hour
    return hour >= 23 or hour < 6


def _curfew_deferral(bot_id: str) -> bool:
    return is_curfew_time() and bot_id in CURFEW_BOT_IDS


@driver.on_startup
async def load_curfew_config():
    _load_curfew_config()
    try:
        from plugins.airi_switch import dedup

        dedup.register_deferral(_curfew_deferral)
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>宵禁降级注册失败，多bot去重让路不生效: {e}</y>")
    logger.opt(colors=True).info(
        f"<y>宵禁机制已加载: bot白名单={CURFEW_BOT_IDS}, 插件白名单={CURFEW_PLUGIN_WHITELIST}</y>"
    )


def get_session_key() -> str:
    now = datetime.datetime.now()
    if now.hour < 6:
        now = now - datetime.timedelta(days=1)
    return now.strftime("%Y-%m-%d")


@run_preprocessor
async def curfew_check(matcher: Matcher, bot: Bot, event: Event):
    bot_id = str(bot.self_id)
    if bot_id not in CURFEW_BOT_IDS:
        return
    if not is_curfew_time():
        if notified_groups:
            notified_groups.clear()
        return
    plugin_name = matcher.plugin_name or ""
    if plugin_name in CURFEW_PLUGIN_WHITELIST:
        return

    if isinstance(event, GroupMessageEvent):
        session = get_session_key()
        for stale in [k for k in notified_groups if k != session]:
            del notified_groups[stale]
        group_id = str(event.group_id)
        if group_id not in notified_groups[session]:
            notified_groups[session].add(group_id)
            hour = datetime.datetime.now().hour
            msg = CURFEW_MESSAGES[0] if hour >= 23 else CURFEW_MESSAGES[1]
            try:
                await bot.send_group_msg(group_id=event.group_id, message=msg)
            except Exception:
                pass

    raise IgnoredException("宵禁时间")
