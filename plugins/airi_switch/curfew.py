import random
import datetime
from collections import defaultdict
from nonebot import get_driver, logger
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent

driver = get_driver()
config = driver.config

CURFEW_BOT_IDS = set()
CURFEW_PLUGIN_WHITELIST = set()
notified_groups = defaultdict(set)

CURFEW_MESSAGES = [
    "慢慢长夜，该睡觉啦~（哈啊）\n祝你做一个美好的梦！\n明天早上6点之后再来找我吧！晚安！",
    "Zzz......\n（airi似乎正在睡觉）\n旁边有一张字条：\n熬夜伤身体，请一定要早睡！\n闹钟上的定时：6:00 AM",
]

@driver.on_startup
async def load_curfew_config():
    global CURFEW_BOT_IDS, CURFEW_PLUGIN_WHITELIST
    bot_ids = getattr(config, "curfew_bot_ids", [])
    CURFEW_BOT_IDS = set(str(bid) for bid in bot_ids)
    whitelist = getattr(config, "curfew_plugin_whitelist", [])
    CURFEW_PLUGIN_WHITELIST = set(whitelist)
    logger.opt(colors=True).info(
        f"<y>宵禁机制已加载: bot白名单={CURFEW_BOT_IDS}, 插件白名单={CURFEW_PLUGIN_WHITELIST}</y>"
    )

def is_curfew_time() -> bool:
    hour = datetime.datetime.now().hour
    return hour >= 23 or hour < 6

def get_today_date() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")

@event_preprocessor
async def curfew_check(bot: Bot, event: Event):
    bot_id = str(bot.self_id)
    if bot_id not in CURFEW_BOT_IDS:
        return
    if not is_curfew_time():
        today = get_today_date()
        if today in notified_groups:
            del notified_groups[today]
        return
    plugin_module = getattr(event, "__module__", "")
    if any(plugin_module.startswith(f"plugins.{p}") for p in CURFEW_PLUGIN_WHITELIST):
        return

    if isinstance(event, GroupMessageEvent):
        today = get_today_date()
        group_id = str(event.group_id)
        if group_id not in notified_groups[today]:
            notified_groups[today].add(group_id)
            if random.randint(1, 3) == 1:
                hour = datetime.datetime.now().hour
                msg = CURFEW_MESSAGES[0] if hour >= 23 else CURFEW_MESSAGES[1]
                try:
                    await bot.send_group_msg(group_id=event.group_id, message=msg)
                except Exception:
                    pass

    raise IgnoredException("Curfew time")

