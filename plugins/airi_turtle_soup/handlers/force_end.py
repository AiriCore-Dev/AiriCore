import time
import random
import traceback
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from ..base.matchers import force_end, matcher
from ..base.constants import min_turtle_minutes, max_group_trial
from ..base import state
from ..base.helpers import get_ids, check_data_existance, get_usernick, end_game

@force_end.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        try:
            state.data['group'][gruop_id]['turtle']
        except:
            return
        user_nick = await get_usernick(bot, gruop_id, user_id)
        if user_id != state.data['group'][gruop_id]['turtle']['creator']:
            raise ValueError('❌ 你不是提问的发起者')
        time_passed = (int(time.time()) - state.data['group'][gruop_id]['turtle']['create_time']) // 60
        if time_passed < min_turtle_minutes:
            dmesg = random.choice([
                f"这才过了{time_passed}分钟诶……\n就准备放弃了吗？驳回驳回！",
                f"时间没到呢，离最早宣布放弃时限还有{min_turtle_minutes-time_passed}分钟！"
            ])
            raise ValueError(dmesg)
        await end_game("break", gruop_id, bot, user_id, user_nick, max_group_trial, matcher)
        return
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)
