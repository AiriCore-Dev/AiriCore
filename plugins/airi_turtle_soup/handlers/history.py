import traceback
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from utils.copy import COPY
from ..base.matchers import history, matcher
from ..base import state
from ..base.helpers import get_ids, check_data_existance

@history.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        gruop_id, user_id = await get_ids(ev)
        if gruop_id is None:
            return
        await check_data_existance(gruop_id, user_id)
        if 'turtle' not in state.data['group'][gruop_id]:
            return
        await bot.send_group_forward_msg(group_id=gruop_id, messages=state.data['group'][gruop_id]['turtle']['history'])
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception:
        logger.error(f"海龟汤历史记录处理失败:\n{traceback.format_exc()}")
        await matcher.send(COPY["PROCESSING_ERROR_LOGGED"], reply_message=True)
