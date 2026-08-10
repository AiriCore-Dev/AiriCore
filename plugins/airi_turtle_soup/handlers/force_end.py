import time
import random
import traceback
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from utils.onebot_query import event_nickname
from ..base.matchers import force_end, matcher
from ..base.constants import min_turtle_minutes, max_group_trial
from ..base import state
from ..base.helpers import get_ids, check_data_existance, end_game

@force_end.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        gruop_id, user_id = await get_ids(ev)
        if gruop_id is None:
            return
        await check_data_existance(gruop_id, user_id)
        if 'turtle' not in state.data['group'][gruop_id]:
            return
        turtle = state.data['group'][gruop_id]['turtle']
        user_nick = event_nickname(ev)
        if user_id != turtle['creator']:
            raise ValueError('❌ 你不是提问的发起者')
        time_passed = (int(time.time()) - turtle['create_time']) // 60
        if time_passed < min_turtle_minutes:
            dmesg = random.choice([
                f"这才过了{time_passed}分钟诶……\n就准备放弃了吗？驳回驳回！",
                f"时间没到呢，离最早宣布放弃时限还有{min_turtle_minutes-time_passed}分钟！"
            ])
            raise ValueError(dmesg)
        await end_game(
            "break",
            gruop_id,
            bot,
            user_id,
            user_nick,
            max_group_trial,
            matcher,
            expected_turtle=turtle,
        )
        return
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception:
        logger.error(f"海龟汤结束海龟汤处理失败:\n{traceback.format_exc()}")
        await matcher.send('❌ 处理时出错了，已记录日志', reply_message=True)
