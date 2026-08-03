import base64
import hashlib
import hmac
import os
import re
import secrets
import time

from . import accounts


CODE_TTL = 300
TOKEN_TTL = 30 * 86400
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
CODE_LEN = 8
CODE_RE = r"[0-9A-Za-z]{6,10}"
EMAIL_CODE_TTL = 300
EMAIL_CODE_ATTEMPTS = 5
_MAX_PENDING = 5000
_PENDING: dict[str, dict] = {}
_email_codes = {}
_SECRET: bytes = b""


def init_secret(value: str = "", data_dir: str = "data/airi_game_server"):
    global _SECRET
    if value:
        _SECRET = value.encode("utf-8")
        return
    key_path = os.path.join(data_dir, "web_token.key")
    legacy_path = os.path.join("data", "airi_daily_check", "web_token.key")
    for path in (key_path, legacy_path):
        try:
            with open(path, "rb") as file:
                _SECRET = file.read().strip()
            if _SECRET:
                if path != key_path:
                    _write_secret(key_path)
                return
        except OSError:
            pass
    _SECRET = secrets.token_hex(32).encode("ascii")
    _write_secret(key_path)


def _write_secret(path: str):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as file:
            file.write(_SECRET)
    except OSError:
        pass


def _gc_pending(now: float):
    expired = [code for code, record in _PENDING.items() if now - record["ts"] > CODE_TTL]
    for code in expired:
        _PENDING.pop(code, None)
    if len(_PENDING) > _MAX_PENDING:
        for code in sorted(_PENDING, key=lambda value: _PENDING[value]["ts"])[:len(_PENDING) - _MAX_PENDING]:
            _PENDING.pop(code, None)


def normalize_code(code: str) -> str:
    return str(code or "").strip().upper()


def new_code() -> str:
    now = time.time()
    _gc_pending(now)
    for _ in range(20):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))
        if code not in _PENDING:
            _PENDING[code] = {"qq": None, "nick": "", "ts": now}
            return code
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))
    _PENDING[code] = {"qq": None, "nick": "", "ts": now}
    return code


def confirm_code(code: str, qq: str, nick: str) -> bool:
    record = _PENDING.get(normalize_code(code))
    if record is None:
        return False
    if time.time() - record["ts"] > CODE_TTL:
        _PENDING.pop(normalize_code(code), None)
        return False
    record["qq"] = str(qq)
    record["nick"] = nick or str(qq)
    return True


def poll_code(code: str):
    code = normalize_code(code)
    record = _PENDING.get(code)
    if record is None:
        return None
    if time.time() - record["ts"] > CODE_TTL:
        _PENDING.pop(code, None)
        return None
    if record["qq"] is None:
        return None
    _PENDING.pop(code, None)
    return record["qq"], record["nick"]


def _sign(payload: str) -> str:
    signature = hmac.new(_SECRET, payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def issue_token(qq: str) -> str:
    expiry = int(time.time()) + TOKEN_TTL
    payload = f"{qq}.{expiry}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> str | None:
    if not token:
        return None
    try:
        qq, expiry, signature = token.rsplit(".", 2)
    except ValueError:
        return None
    payload = f"{qq}.{expiry}"
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        if int(expiry) < time.time():
            return None
    except ValueError:
        return None
    return qq


def request_bot_code() -> tuple[str, int]:
    return new_code(), CODE_TTL


def confirm_bot_code(code: str, qq: str, nick: str) -> bool:
    return confirm_code(code, qq, nick)


def poll_bot_code(code: str):
    return poll_code(code)


def set_nick(qq: str, nick: str):
    account = accounts.ensure_account(qq)
    account["web_nick"] = nick


def parse_qq_email(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+@qq\.com", value) is None:
        raise ValueError("邮箱格式应为 QQ号@qq.com")
    return value[:-7]


def _digest(qq: str, code: str) -> str:
    return hashlib.sha256(f"{qq}:{code}".encode()).hexdigest()


def create_email_code(qq: str) -> str:
    now = time.time()
    if len(_email_codes) >= _MAX_PENDING:
        expired = [
            account
            for account, record in _email_codes.items()
            if record["expires"] < now
        ]
        for account in expired:
            _email_codes.pop(account, None)
    if len(_email_codes) >= _MAX_PENDING:
        oldest = min(_email_codes, key=lambda account: _email_codes[account]["expires"])
        _email_codes.pop(oldest, None)
    code = f"{secrets.randbelow(1000000):06d}"
    _email_codes[qq] = {"digest": _digest(qq, code), "expires": now + EMAIL_CODE_TTL, "attempts": 0}
    return code


def discard_email_code(qq: str) -> None:
    _email_codes.pop(qq, None)


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
