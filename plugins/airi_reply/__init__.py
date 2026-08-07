import os
import time
from nonebot import on_startswith
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from utils.cache import get_b64

reply_interval = 60
last_notice: dict = {}


def _session(ev: MessageEvent) -> str:
    if isinstance(ev, GroupMessageEvent):
        return f"group_{ev.group_id}"
    return f"user_{ev.user_id}"


def _cooldown_passed(key) -> bool:
    now = time.time()
    for k in [k for k, t in last_notice.items() if now - t > reply_interval * 10]:
        last_notice.pop(k, None)
    if now - last_notice.get(key, 0) <= reply_interval:
        return False
    last_notice[key] = now
    return True


async def _send(matcher, ev: MessageEvent, name: str):
    if not _cooldown_passed((name, _session(ev))):
        return
    b64 = get_b64(os.path.join(os.path.dirname(__file__), name))
    if not b64:
        return
    await matcher.send(MessageSegment.record(b64))


dklmt = on_startswith(('打卡啦摩托', '打卡拉摩托', '大卡拉摩托', '大卡啦摩托'), priority=99)
wdh = on_startswith(('汪大吼', 'wonderhoi', 'wonderhoy', 'わんだほ~い '), priority=99, ignorecase=True)


@dklmt.handle()
async def _(bot: Bot, ev: MessageEvent):
    await _send(dklmt, ev, 'dklmt.wav')


@wdh.handle()
async def _(bot: Bot, ev: MessageEvent):
    await _send(wdh, ev, 'wdh.wav')
