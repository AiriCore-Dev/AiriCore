import binascii
import re

from nonebot import get_driver
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.message import event_preprocessor
from nonebot.permission import Permission

from .totp_2fa import totp_verify


_CODE_RE = re.compile(r"^\d{6}$")
_VERIFIED_ATTR = "_airicore_superuser_2fa_verified"
def _driver_config():
    return get_driver().config


def extract_2fa_code(text: str) -> tuple[str | None, str]:
    """Extract a six-digit code immediately before or after a command."""
    normalized = str(text or "").strip()
    tokens = list(re.finditer(r"\S+", normalized))
    candidates = tokens[:3]
    for token in candidates:
        code = token.group(0)
        if not _CODE_RE.fullmatch(code):
            continue
        before = normalized[: token.start()].rstrip()
        after = normalized[token.end() :].lstrip()
        if before and after:
            return code, f"{before} {after}"
        return code, before or after
    return None, normalized


def strip_2fa_code(text: str) -> str:
    return extract_2fa_code(text)[1]


def _configured_secret() -> str:
    return str(getattr(_driver_config(), "_2fa_key", "") or "").strip()


def _configured_superusers() -> set[str]:
    return {str(user_id) for user_id in getattr(_driver_config(), "superusers", ())}


def is_verified_superuser(event: Event) -> bool:
    return bool(
        getattr(event, _VERIFIED_ATTR, False)
        and str(getattr(event, "user_id", "")) in _configured_superusers()
    )


async def _check_superuser_2fa(bot: Bot, event: Event) -> bool:
    return is_verified_superuser(event)


SUPERUSER_2FA = Permission(_check_superuser_2fa)


def _strip_2fa_from_message(message):
    segments = list(message)
    for index, segment in enumerate(segments):
        if not isinstance(segment, MessageSegment) or not segment.is_text():
            continue
        code, normalized = extract_2fa_code(segment.data.get("text", ""))
        if code is None:
            return message
        segments[index] = MessageSegment.text(normalized)
        return message.__class__(segments)
    return message


@event_preprocessor
async def superuser_2fa_preprocessor(event: Event):
    if not isinstance(event, MessageEvent):
        return
    if str(getattr(event, "user_id", "")) not in _configured_superusers():
        return

    code, _ = extract_2fa_code(event.get_plaintext())
    if code is None:
        return
    try:
        verified = totp_verify(_configured_secret(), code)
    except (binascii.Error, TypeError, ValueError):
        verified = False
    if not verified:
        return

    setattr(event, _VERIFIED_ATTR, True)
    event.message = _strip_2fa_from_message(event.message)
