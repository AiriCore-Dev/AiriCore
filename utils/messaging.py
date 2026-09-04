from dataclasses import dataclass
from typing import Optional

from nonebot import logger
from nonebot.matcher import Matcher
from nonebot_plugin_alconna import Target, UniMessage, get_target


_scene_membership_checker = None


def register_scene_membership_checker(callback):
    global _scene_membership_checker
    _scene_membership_checker = callback


def choose_notification_bot(bots, configured_account):
    if not bots:
        return None
    normalized = {str(key): value for key, value in bots.items()}
    account = str(configured_account or "").strip()
    if account and account in normalized:
        return normalized[account]
    return normalized[sorted(normalized)[0]]


def _normalize_bots(bots):
    if not bots:
        return {}
    return {str(key): value for key, value in bots.items() if value is not None}


def _resolve_bot_id(bot):
    if bot is None:
        return None
    bot_id = getattr(bot, "self_id", bot)
    bot_id = str(bot_id).strip()
    return bot_id or None


def _resolve_order(bots, configured_account, preferred=None):
    normalized = _normalize_bots(bots)
    if not normalized:
        return normalized, []
    ordered = []
    seen = set()
    for candidate in (
        _resolve_bot_id(preferred),
        str(configured_account or "").strip() or None,
    ):
        if candidate and candidate in normalized and candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    for bot_id in sorted(normalized):
        if bot_id not in seen:
            ordered.append(bot_id)
            seen.add(bot_id)
    return normalized, ordered


def select_bot(bots, configured_account, *, preferred=None):
    normalized, ordered = _resolve_order(bots, configured_account, preferred=preferred)
    if not ordered:
        return None
    return normalized[ordered[0]]


@dataclass(frozen=True, slots=True)
class SendResult:
    sent: bool
    bot_id: Optional[str]
    error: Optional[BaseException]


async def send_group_with_fallback(
    message,
    *,
    group_id,
    preferred=None,
    configured_account=None,
    bots=None,
    tag="群消息",
):
    import nonebot

    normalized, ordered = _resolve_order(
        nonebot.get_bots() if bots is None else bots,
        configured_account,
        preferred=preferred,
    )
    last_error = None
    last_bot_id = None
    for bot_id in ordered:
        bot = normalized[bot_id]
        last_bot_id = bot_id
        try:
            await bot.send_group_msg(group_id=group_id, message=message)
            return SendResult(True, bot_id, None)
        except Exception as error:
            last_error = error
            logger.warning(f"{tag}发送失败（{bot_id}）：{error}")
    return SendResult(False, last_bot_id, last_error)


def get_notification_bot(fallback=None):
    import nonebot
    bots = nonebot.get_bots()
    try:
        configured = getattr(nonebot.get_driver().config, "notification_bot_account", "") or ""
    except Exception:
        configured = ""
    return choose_notification_bot(bots, configured) or fallback


def _known_in_scene(bot_id: str, scene: str) -> bool:
    checker = _scene_membership_checker
    if checker is None:
        return True
    try:
        return checker(bot_id, scene) is not False
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
