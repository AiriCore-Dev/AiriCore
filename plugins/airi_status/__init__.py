import asyncio
import base64
import time
from pathlib import Path

from nonebot.rule import Rule
from utils.superuser_2fa import SUPERUSER_2FA
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from nonebot import on_fullmatch, logger
from .config import Config
from .config import config as plugin_config

from .drawer import draw
from utils.onebot_query import bot_name
from utils.cache import get_image, register_asset_group, value_bytes

register_asset_group("airi_status 素材", Path(__file__).resolve().parent / "resources" / "images", ("*.png", "*.jpg", "*.jpeg"), lambda path: value_bytes(get_image(path)))

COOLDOWN = 0
_last_call: dict = {}
_render_lock = asyncio.Lock()


def to_me() -> Rule:
    if plugin_config.to_me:
        from nonebot.rule import to_me as _rule

        return _rule()

    async def _to_me() -> bool:
        return True

    return Rule(_to_me)


status = on_fullmatch(
    ("status", "状态"),
    block=True,
    priority=20,
    permission=SUPERUSER_2FA if plugin_config.only_superuser else None,
)


def _session(ev: MessageEvent) -> str:
    if isinstance(ev, GroupMessageEvent):
        return f"group_{ev.group_id}"
    return f"user_{ev.user_id}"


def _cooldown_left(key: str) -> float:
    now = time.time()
    for k, t in [(k, t) for k, t in _last_call.items() if now - t > COOLDOWN * 20]:
        _last_call.pop(k, None)
    left = COOLDOWN - (now - _last_call.get(key, 0))
    return left if left > 0 else 0


def _cooldown_commit(key: str) -> None:
    _last_call[key] = time.time()


@status.handle()
async def _(bot: Bot, ev: MessageEvent):
    key = _session(ev)
    left = _cooldown_left(key)
    if left > 0:
        await status.finish(f"状态图刚生成过，请 {int(left) + 1} 秒后再试~")
    if _render_lock.locked():
        await status.finish("正在生成状态图，请稍等~")
    nickname = await bot_name(bot, "Momoi Airi")
    async with _render_lock:
        try:
            data = await asyncio.to_thread(draw, nickname)
        except Exception as e:
            logger.opt(exception=e).error("状态图生成失败")
            await status.finish(f"状态图生成失败: {type(e).__name__}: {e}")
    try:
        await status.send(
            MessageSegment.image("base64://" + base64.b64encode(data).decode())
        )
    except Exception as e:
        logger.opt(exception=e).error("状态图发送失败")
        await status.finish(f"状态图发送失败: {type(e).__name__}: {e}")
    _cooldown_commit(key)
