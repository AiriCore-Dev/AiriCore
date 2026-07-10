from utils.totp_2fa import totp_verify
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from ..base.matchers import superuser_debug
from ..base.constants import _2fa_key
from ..base import state
from ..base.persistence import daily_clear, save_to_json, save_data_backup, load_json

@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    session_id = str(ev.get_session_id())
    if 'group' in session_id:
        split_id = session_id.split("_")
        user_id = split_id[2]
        gruop_id = split_id[1]
    else:
        user_id = session_id
        gruop_id = None
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  ", " ")) != src:
        src = tmpa
    user_2fa_digit = src[:6]
    if not totp_verify(_2fa_key, user_2fa_digit):
        await superuser_debug.finish('2fa verification failed')
    src = src[6:].strip()
    user_nick = ev.sender.card or ev.sender.nickname
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
    elif src[:6] == 'await ':
        try:
            try: res = await eval(src[6:])
            except: res = await exec(src[6:])
        except Exception as err:
            res = '出错了: ' + repr(err)
        else:
            res = '命令执行成功' if not res else str(res)
    else:
        try:
            try: res = eval(src)
            except: res = exec(src)
        except Exception as err:
            res = '出错了: ' + repr(err)
        else:
            res = '命令执行成功' if not res else str(res)
    await superuser_debug.finish(res, reply_message=True)
