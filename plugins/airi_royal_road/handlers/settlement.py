from ..base.matchers import settlement
from ..render import output
from ..service import service
from nonebot.adapters.onebot.v11 import MessageEvent


@settlement.handle()
async def handle_settlement(event: MessageEvent):
    user_id = str(event.get_user_id())
    response = await service.status_view(user_id)
    await settlement.finish(output.text_fallback("王道结算将在活动结束后开放") + response.image)
