import traceback

from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from ..base.matchers import superuser_debug
from ..base import state
from ..base.persistence import daily_clear, save_to_json, save_data_backup, load_json
from utils.copy import COPY

@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
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
    else:
        awaited = src[:6] == 'await '
        expr = src[6:].lstrip() if awaited else src
        ctx = {**globals(), 'bot': bot, 'ev': ev}
        try:
            try:
                res = eval(compile(expr, '<tdebug>', 'eval'), ctx)
            except SyntaxError:
                res = exec(compile(expr, '<tdebug>', 'exec'), ctx)
            if awaited and hasattr(res, '__await__'):
                res = await res
        except Exception:
            res = traceback.format_exc()
        else:
            res = COPY["COMMAND_SUCCESS"] if not res else str(res)
    await superuser_debug.finish(res, reply_message=True)
