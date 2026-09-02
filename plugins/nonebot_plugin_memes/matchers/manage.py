from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, PRIVATE
from nonebot_plugin_alconna import Alconna, Args, on_alconna
from utils.superuser_2fa import SUPERUSER_2FA

from ..manager import MemeMode, meme_manager
from .utils import UserId, find_meme


PERM_EDIT = SUPERUSER_2FA | PRIVATE | GROUP_OWNER | GROUP_ADMIN
PERM_GLOBAL = SUPERUSER_2FA


block_matcher = on_alconna(
    Alconna("禁用表情", Args["meme_name", str]),
    block=True,
    priority=11,
    use_cmd_start=True,
    permission=PERM_EDIT,
)
unblock_matcher = on_alconna(
    Alconna("启用表情", Args["meme_name", str]),
    block=True,
    priority=11,
    use_cmd_start=True,
    permission=PERM_EDIT,
)
block_gl_matcher = on_alconna(
    Alconna("全局禁用表情", Args["meme_name", str]),
    block=True,
    priority=11,
    use_cmd_start=True,
    permission=PERM_GLOBAL,
)
unblock_gl_matcher = on_alconna(
    Alconna("全局启用表情", Args["meme_name", str]),
    block=True,
    priority=11,
    use_cmd_start=True,
    permission=PERM_GLOBAL,
)


@block_matcher.handle()
async def _(matcher: Matcher, user_id: UserId, meme_name: str):
    meme = await find_meme(matcher, meme_name)
    meme_manager.block(user_id, meme.key)
    await matcher.finish(f"表情 {meme.key} 禁用成功")


@unblock_matcher.handle()
async def _(matcher: Matcher, user_id: UserId, meme_name: str):
    meme = await find_meme(matcher, meme_name)
    meme_manager.unblock(user_id, meme.key)
    await matcher.finish(f"表情 {meme.key} 启用成功")


@block_gl_matcher.handle()
async def _(matcher: Matcher, meme_name: str):
    meme = await find_meme(matcher, meme_name)
    meme_manager.change_mode(MemeMode.WHITE, meme.key)
    await matcher.finish(f"表情 {meme.key} 已设为白名单模式")


@unblock_gl_matcher.handle()
async def _(matcher: Matcher, meme_name: str):
    meme = await find_meme(matcher, meme_name)
    meme_manager.change_mode(MemeMode.BLACK, meme.key)
    await matcher.finish(f"表情 {meme.key} 已设为黑名单模式")
