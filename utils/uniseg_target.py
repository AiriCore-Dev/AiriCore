from typing import Optional

from nonebot import logger
from nonebot.matcher import Matcher
from nonebot_plugin_alconna import Target, UniMessage, get_target


def _known_in_scene(bot_id: str, scene: str) -> bool:
    try:
        from plugins.airi_switch import dedup
    except Exception:
        return True
    try:
        return dedup.in_group(bot_id, scene) is not False
    except Exception:
        return True


def capture_target() -> Optional[Target]:
    try:
        target = get_target()
    except Exception:
        return None
    origin = str(target.self_id or "")
    base = target.selector

    async def _selector(bot) -> bool:
        if base is not None and not await base(bot):
            return False
        if str(bot.self_id) == origin:
            return True
        if target.private:
            return False
        return _known_in_scene(str(bot.self_id), target.parent_id or target.id)

    target.selector = _selector
    return target


async def send_with_fallback(matcher: Matcher, msg: str, target: Optional[Target],
                             tag: str = "延迟提醒") -> None:
    if target is not None:
        try:
            await UniMessage.text(msg).send(target=target)
            return
        except Exception as e:
            logger.warning(f"{tag}发送失败，改用当前会话重试: {e}")
    try:
        await matcher.send(msg)
    except Exception as e:
        logger.warning(f"{tag}发送失败: {e}")
