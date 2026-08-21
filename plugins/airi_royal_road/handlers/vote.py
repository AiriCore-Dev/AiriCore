from ..base.matchers import vote
from ..base.locks import world_lock
from ..base.state import get_world
from ..render import output
from nonebot.adapters.onebot.v11 import MessageEvent


@vote.handle()
async def handle_vote(event: MessageEvent):
    async with world_lock("current"):
        get_world()
        await vote.finish(output.render_response("王道投票将在周五晨星节点后开放"))
