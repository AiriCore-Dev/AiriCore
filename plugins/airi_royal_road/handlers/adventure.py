from ..base.matchers import adventure, choice
from ..base.locks import user_lock
from ..base.state import get_personal
from ..render import output
from nonebot.adapters.onebot.v11 import MessageEvent


@adventure.handle()
async def handle_adventure(event: MessageEvent):
    user_id = str(event.get_user_id())
    async with user_lock(user_id):
        get_personal(user_id)
        await adventure.finish(output.render_response("王道征途的规则引擎正在准备中"))


@choice.handle()
async def handle_choice(event: MessageEvent):
    user_id = str(event.get_user_id())
    async with user_lock(user_id):
        get_personal(user_id)
        await choice.finish(output.render_response("当前还没有可确认的征途选项"))
