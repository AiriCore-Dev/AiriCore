import traceback
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from utils.copy import COPY
from ..base.matchers import times_used, matcher
from ..base.constants import max_player_query_trial, max_player_truth_trial, max_group_trial, max_group_turtle_perday
from ..base import state
from ..base.helpers import get_ids, check_data_existance

@times_used.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        gruop_id, user_id = await get_ids(ev)
        if gruop_id is None:
            return
        await check_data_existance(gruop_id, user_id)
        if 'turtle' not in state.data['group'][gruop_id]:
            return
        res = f"本场游戏：\n  -本人已提问次数：{state.data['group'][gruop_id]['turtle']['players'][user_id]['query_trial']}/{max_player_query_trial}\n  -本人已猜汤底次数：{state.data['group'][gruop_id]['turtle']['players'][user_id]['truth_trial']}/{max_player_truth_trial}\n  -群总轮询次数：{state.data['group'][gruop_id]['turtle']['trial']}/{max_group_trial}\n\n本群：\n  -群今日已进行游戏场数：{state.data['group'][gruop_id]['times']}/{max_group_turtle_perday}"
        await matcher.send(res, reply_message=True)
        return
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception:
        logger.error(f"海龟汤次数查询处理失败:\n{traceback.format_exc()}")
        await matcher.send(COPY["PROCESSING_ERROR_LOGGED"], reply_message=True)
