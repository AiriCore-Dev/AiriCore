from ..base.matchers import archive, help, map_view, status
from ..base.locks import user_lock
from ..base.state import get_personal
from ..render import output
from nonebot.adapters.onebot.v11 import MessageEvent


@map_view.handle()
async def handle_map(event: MessageEvent):
    async with user_lock(str(event.get_user_id())):
        get_personal(str(event.get_user_id()))
        await map_view.finish(output.render_response("王道地图将在活动开启后显示"))


@status.handle()
async def handle_status(event: MessageEvent):
    async with user_lock(str(event.get_user_id())):
        get_personal(str(event.get_user_id()))
        await status.finish(output.render_response("王道状态将在活动开启后显示"))


@archive.handle()
async def handle_archive(event: MessageEvent):
    async with user_lock(str(event.get_user_id())):
        get_personal(str(event.get_user_id()))
        await archive.finish(output.render_response("王道图鉴将在活动开启后显示"))


@help.handle()
async def handle_help(event: MessageEvent):
    async with user_lock(str(event.get_user_id())):
        get_personal(str(event.get_user_id()))
        await help.finish(output.render_response("王道帮助将在活动开启后显示"))
