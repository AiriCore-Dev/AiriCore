from ..base.matchers import vote
from ..render import output


@vote.handle()
async def handle_vote():
    await vote.finish(output.render_response("王道投票将在周五晨星节点后开放"))
