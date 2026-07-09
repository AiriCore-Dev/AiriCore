"""运行状态"""

#from nonebot import require
import base64
from nonebot.rule import Rule
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from nonebot import on_command, on_fullmatch
from .config import Config
from .config import config as plugin_config

from .drawer import draw


def to_me() -> Rule:
    if plugin_config.to_me:
        from nonebot.rule import to_me

        return to_me()

    async def _to_me() -> bool:
        return True

    return Rule(_to_me)


status = on_fullmatch(("status","状态"), block=True)

@status.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        login_info = await bot.get_login_info()
        nickname = login_info.get("nickname") or "Momoi Airi"
    except Exception:
        nickname = "Momoi Airi"
    await status.finish(MessageSegment.image("base64://" + base64.b64encode(draw(nickname)).decode()))
    
