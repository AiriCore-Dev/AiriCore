import hashlib
import hmac
import secrets
import time

from plugins.airi_daily_check.roguelike import auth as legacy_auth
from plugins.airi_daily_check.roguelike import store


CODE_RE = legacy_auth.CODE_RE
EMAIL_CODE_TTL = 300
EMAIL_CODE_ATTEMPTS = 5
_email_codes = {}


def init_secret(value: str = ""):
    legacy_auth.init_secret(value)


def issue_token(qq: str) -> str:
    return legacy_auth.issue_token(qq)


def verify_token(token: str) -> str | None:
    return legacy_auth.verify_token(token)


def request_bot_code() -> tuple[str, int]:
    return legacy_auth.new_code(), legacy_auth.CODE_TTL


def confirm_bot_code(code: str, qq: str, nick: str) -> bool:
    return legacy_auth.confirm_code(code, qq, nick)


def poll_bot_code(code: str):
    return legacy_auth.poll_code(code)


def set_nick(qq: str, nick: str):
    account = store.ensure_account(qq)
    account["web_nick"] = nick


def parse_qq_email(value: str) -> str:
    if not isinstance(value, str) or not value.endswith("@qq.com"):
        raise ValueError("邮箱格式应为 QQ号@qq.com")
    qq = value[:-7]
    if not qq.isdigit() or not qq:
        raise ValueError("邮箱格式应为 QQ号@qq.com")
    return qq


def _digest(qq: str, code: str) -> str:
    return hashlib.sha256(f"{qq}:{code}".encode()).hexdigest()


def create_email_code(qq: str) -> str:
    code = f"{secrets.randbelow(1000000):06d}"
    _email_codes[qq] = {"digest": _digest(qq, code), "expires": time.time() + EMAIL_CODE_TTL, "attempts": 0}
    return code


def confirm_email_code(qq: str, code: str) -> bool:
    record = _email_codes.get(qq)
    if record is None or record["expires"] < time.time() or record["attempts"] >= EMAIL_CODE_ATTEMPTS:
        _email_codes.pop(qq, None)
        return False
    record["attempts"] += 1
    if not hmac.compare_digest(record["digest"], _digest(qq, code)):
        return False
    _email_codes.pop(qq, None)
    return True
