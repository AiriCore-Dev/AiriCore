from ..base.matchers import settlement
from ..render import output


@settlement.handle()
async def handle_settlement():
    await settlement.finish(output.render_response("王道结算将在活动结束后开放"))
