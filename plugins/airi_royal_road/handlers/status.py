from ..base.matchers import archive, help, map_view, status
from ..render import output


@map_view.handle()
async def handle_map():
    await map_view.finish(output.render_response("王道地图将在活动开启后显示"))


@status.handle()
async def handle_status():
    await status.finish(output.render_response("王道状态将在活动开启后显示"))


@archive.handle()
async def handle_archive():
    await archive.finish(output.render_response("王道图鉴将在活动开启后显示"))


@help.handle()
async def handle_help():
    await help.finish(output.render_response("王道帮助将在活动开启后显示"))
