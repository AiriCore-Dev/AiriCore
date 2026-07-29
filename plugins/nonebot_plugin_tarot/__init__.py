from nonebot import on_command, on_startswith
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata

from .data_source import tarot_manager

__tarot_version__ = "v0.4.0.post4"
__tarot_usages__ = f'''
塔罗牌 {__tarot_version__}
[占卜] 随机选取牌阵进行占卜
[塔罗牌] 得到单张塔罗牌回应'''.strip()

__plugin_meta__ = PluginMetadata(
    name="塔罗牌",
    description="塔罗牌！魔法占卜🔮",
    usage=__tarot_usages__,
    extra={
        "author": "KafCoppelia <k740677208@gmail.com>",
        "version": __tarot_version__
    }
)

divine = on_startswith("占卜", priority=7)
tarot = on_command(cmd="塔罗牌", priority=7)


@divine.handle()
async def general_divine(bot: Bot, matcher: Matcher, event: MessageEvent):
    arg: str = event.get_plaintext()

    if "帮助" in arg[-2:]:
        await matcher.finish(__tarot_usages__)

    await tarot_manager.divine(bot, matcher, event, argd if len(argd := arg[2:].lstrip()) else '无牌阵')


@tarot.handle()
async def _(matcher: Matcher, event: MessageEvent):
    arg: str = event.get_plaintext()

    if "帮助" in arg[-2:]:
        await matcher.finish(__tarot_usages__)

    msg = await tarot_manager.onetime_divine()
    await matcher.finish(msg, reply_message=True)
