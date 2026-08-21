from ..base.matchers import settlement
from ..base.locks import settlement_lock
from ..base.state import get_personal
from ..render import output
from nonebot.adapters.onebot.v11 import MessageEvent


@settlement.handle()
async def handle_settlement(event: MessageEvent):
    user_id = str(event.get_user_id())
    async with settlement_lock(user_id):
        get_personal(user_id)
        await settlement.finish(output.render_response("王道结算将在活动结束后开放"))
