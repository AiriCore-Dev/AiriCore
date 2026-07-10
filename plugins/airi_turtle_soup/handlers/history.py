import traceback
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from ..base.matchers import history, matcher
from ..base import state
from ..base.helpers import get_ids, check_data_existance

@history.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        try:
            state.data['group'][gruop_id]['turtle']
        except:
            return
        await bot.send_group_forward_msg(group_id=gruop_id, messages=state.data['group'][gruop_id]['turtle']['history'])
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)
