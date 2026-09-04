import traceback

from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from utils.copy import COPY

from .base.state import driver, data, email_list
from .base import state
from .base.matchers import *
from .base.helpers import *
from .base.persistence import (
    email_login,
    load_json,
    save_to_json,
    daily_clear,
    save_data_backup,
    flush_email_queue,
    timings,
)
from . import handlers


@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    global data
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  "," ")) != src:
        src = tmpa
    if not src:
        await superuser_debug.finish(COPY["MISSING_EXPRESSION"])
    if src == 'reset':
        await daily_clear()
        res = f'刷新一天：{COPY["COMMAND_SUCCESS"]}'
    elif src == 'save':
        await save_to_json()
        res = f'存档：{COPY["COMMAND_SUCCESS"]}'
    elif src == 'backup':
        await save_data_backup()
        res = f'备份：{COPY["COMMAND_SUCCESS"]}'
    elif src == 'load':
        await load_json()
        res = f'读档：{COPY["COMMAND_SUCCESS"]}'
    elif src == 'email':
        res = await email_login()
    elif src == 'sendemail':
        res = await flush_email_queue()
    else:
        awaited = src[:6] == 'await '
        expr = src[6:].lstrip() if awaited else src
        user_id, group_id, user_nick = _debug_session(ev)
        ctx = {
            **globals(), 'bot': bot, 'ev': ev,
            'user_id': user_id, 'group_id': group_id, 'user_nick': user_nick,
        }
        try:
            try:
                res = eval(compile(expr, '<btdebug>', 'eval'), ctx)
            except SyntaxError:
                res = exec(compile(expr, '<btdebug>', 'exec'), ctx)
            if awaited and hasattr(res, '__await__'):
                res = await res
        except Exception:
            res = traceback.format_exc()
        else:
            res = COPY["COMMAND_SUCCESS"] if not res else str(res)
    await superuser_debug.finish(res, reply_message = True)
