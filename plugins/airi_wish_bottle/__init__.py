import traceback

from utils.totp_2fa import totp_verify
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from .base.state import driver, _2fa_key, data, email_list
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
    if not _2fa_key:
        await superuser_debug.finish('未配置 _2fa_key，调试通道已禁用')
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  "," ")) != src:
        src = tmpa
    user_2fa_digit = src[:6]
    if not totp_verify(_2fa_key, user_2fa_digit):
        await superuser_debug.finish('2fa verification failed')
    src = src[6:].strip()
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
            res = '命令执行成功' if not res else str(res)
    await superuser_debug.finish(res, reply_message = True)
