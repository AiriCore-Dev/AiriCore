from ..base.matchers import adventure, choice
from ..render import output


@adventure.handle()
async def handle_adventure():
    await adventure.finish(output.render_response("王道征途的规则引擎正在准备中"))


@choice.handle()
async def handle_choice():
    await choice.finish(output.render_response("当前还没有可确认的征途选项"))
