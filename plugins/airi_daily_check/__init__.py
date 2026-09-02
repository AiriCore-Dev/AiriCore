import asyncio
import random
import traceback

from nonebot import get_driver
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

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
        await superuser_debug.finish('缺少要执行的表达式')

    if src == 'reset':
        await daily_clear()
        res = '刷新一天：命令执行成功'
    elif src == 'save':
        await save_to_json()
        res = '存档：命令执行成功'
    elif src == 'backup':
        await save_data_backup()
        res = '备份：命令执行成功'
    elif src == 'load':
        await load_json()
        res = '读档：命令执行成功'
    elif src == 'rdc':
        await asyncio.to_thread(reset_daily_challenge)
        res = '重置每日挑战：命令执行成功'
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
            res = '命令执行成功' if not res else str(res)
    await superuser_debug.finish(res, reply_message=True)
