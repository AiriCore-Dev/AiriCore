from ..base.matchers import archive, help, map_view, status
from ..service import service
from ..render import output
from nonebot.adapters.onebot.v11 import MessageEvent


@map_view.handle()
async def handle_map(event: MessageEvent):
    response = await service.map_view(str(event.get_user_id()))
    await map_view.finish(output.text_fallback(response.fallback_text) + response.image)


@status.handle()
async def handle_status(event: MessageEvent):
    response = await service.status_view(str(event.get_user_id()))
    await status.finish(output.text_fallback(response.fallback_text) + response.image)


@archive.handle()
async def handle_archive(event: MessageEvent):
    response = await service.archive_view(str(event.get_user_id()))
    await archive.finish(output.text_fallback(response.fallback_text) + response.image)


@help.handle()
async def handle_help(event: MessageEvent):
    response = await service.help_view(str(event.get_user_id()))
    await help.finish(output.text_fallback(response.fallback_text) + response.image)
