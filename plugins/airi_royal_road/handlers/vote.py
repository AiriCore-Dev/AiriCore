from ..base.matchers import vote
from ..render import output
from ..service import service
from nonebot.adapters.onebot.v11 import MessageEvent


@vote.handle()
async def handle_vote(event: MessageEvent):
    response = await service.status_view(str(event.get_user_id()))
    await vote.finish(output.text_fallback("王道投票将在周五晨星节点后开放") + response.image)
