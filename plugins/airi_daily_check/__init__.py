import asyncio
import random
import traceback

from nonebot import get_driver
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from utils.copy import COPY

from .base import cache

from .base import state
from .base.state import data, theme_extension, game_ans
from .base.constants import *
from .base.matchers import *
from .base.helpers import *
from .base.persistence import (
    load_json, save_to_json, daily_clear,
    reset_daily_challenge, save_data_backup, timings,
)
from . import handlers

driver = get_driver()


@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, group_id = parse_session(ev)
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  ", " ")) != src:
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
    elif src == 'rdc':
        await asyncio.to_thread(reset_daily_challenge)
        res = f'重置每日挑战：{COPY["COMMAND_SUCCESS"]}'
    else:
        ctx = {**globals(), 'bot': bot, 'ev': ev}
        try:
            try:
                res = eval(compile(src, '<qdebug>', 'eval'), ctx)
            except SyntaxError:
                res = exec(compile(src, '<qdebug>', 'exec'), ctx)
        except Exception:
            res = traceback.format_exc()
        else:
            res = COPY["COMMAND_SUCCESS"] if not res else str(res)
    await superuser_debug.finish(res, reply_message=True)
