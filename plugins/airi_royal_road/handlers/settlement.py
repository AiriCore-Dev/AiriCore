from ..base.matchers import settlement
from ..render import output
from ..service import service
from nonebot.adapters.onebot.v11 import MessageEvent


@settlement.handle()
async def handle_settlement(event: MessageEvent):
    user_id = str(event.get_user_id())
    try:
        response = await service.settle(user_id)
    except ValueError as exc:
        response = await service.status_view(user_id)
        await settlement.finish(output.text_fallback(str(exc)) + response.image)
    await settlement.finish(output.text_fallback(response.fallback_text) + response.image)
