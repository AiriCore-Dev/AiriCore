import re

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent, Message, PrivateMessageEvent
from pydantic import PrivateAttr

from utils.superuser_2fa import extract_2fa_code

from .account_admin import Credentials
from .protocol import QueryError
from .renewal import password_digest


def without_nickname(text):
    text = text.lstrip()
    nicknames = sorted(get_driver().config.nickname, key=len, reverse=True)
    if nicknames:
        match = re.match('(?:' + '|'.join(re.escape(name) for name in nicknames) + r')[\s,，]*', text, re.IGNORECASE)
        if match:
            text = text[match.end():]
    return text


def account_text(text):
    _, normalized = extract_2fa_code(text)
    starts = get_driver().config.command_start
    for start in sorted(starts, key=len, reverse=True):
        prefix = start + 'astral'
        if normalized.startswith(prefix) and normalized[len(prefix):][:1].isspace():
            rest = normalized[len(prefix):].lstrip()
            if rest == 'account' or rest.startswith('account') and rest[len('account'):][:1].isspace():
                return rest[len('account'):].strip()
    return None


def scrub_event(event):
    if getattr(event, '_astral_scrubbed', False):
        return
    raw = without_nickname(event.get_plaintext())
    text = account_text(raw)
    if text is None:
        return
    event._astral_scrubbed = True
    event._astral_credentials = None
    action = text.split(maxsplit=1)[0] if text else 'help'
    code, _ = extract_2fa_code(raw)
    if action == 'login':
        allowed = isinstance(event, PrivateMessageEvent) and str(event.user_id) in get_driver().config.superusers
        match = re.fullmatch(r'login[ \t]+(1[0-9]{10})[ \t]+([^\r\n]+)', text)
        if allowed and match and len(text) <= 550 and all(segment.type == 'text' for segment in event.message):
            try:
                event._astral_credentials = Credentials(match[1], password_digest(match[2]))
            except QueryError:
                pass
        text = 'login'
    elif text not in ('', 'help', 'setup', 'refresh', 'check', 'clear confirm') and not re.fullmatch(r'setup[ \t]+[0-9]{9}', text):
        text = 'invalid'
    start = '' if '' in get_driver().config.command_start else sorted(get_driver().config.command_start)[0]
    normalized = start + 'astral ' + (code + ' ' if code else '') + 'account ' + text
    event.message = Message(normalized)
    event.original_message = Message(start + 'astral account [账号管理内容已隐藏]')
    event.raw_message = str(event.original_message)
    event.reply = None


class CredentialEventMixin:
    def __init__(self, **data):
        super().__init__(**data)
        scrub_event(self)

    def get_event_description(self):
        if self._astral_scrubbed:
            return f'账号管理消息 {self.message_id}，内容已隐藏'
        return super().get_event_description()


class CredentialPrivateEvent(CredentialEventMixin, PrivateMessageEvent):
    _astral_credentials: Credentials | None = PrivateAttr(default=None)
    _astral_scrubbed: bool = PrivateAttr(default=False)


class CredentialGroupEvent(CredentialEventMixin, GroupMessageEvent):
    _astral_credentials: Credentials | None = PrivateAttr(default=None)
    _astral_scrubbed: bool = PrivateAttr(default=False)


def install():
    Adapter.add_custom_model(CredentialPrivateEvent, CredentialGroupEvent)
