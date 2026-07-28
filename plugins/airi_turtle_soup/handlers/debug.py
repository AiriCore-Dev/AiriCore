import traceback

from utils.totp_2fa import totp_verify
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from ..base.matchers import superuser_debug
from ..base.constants import _2fa_key
from ..base import state
from ..base.persistence import daily_clear, save_to_json, save_data_backup, load_json

@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    if not str(_2fa_key or "").strip():
        await superuser_debug.finish('未配置 _2fa_key，调试通道已禁用')
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  ", " ")) != src:
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
            res = '命令执行成功' if not res else str(res)
    await superuser_debug.finish(res, reply_message=True)
