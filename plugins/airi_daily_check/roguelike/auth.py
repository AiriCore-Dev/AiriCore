import os
import hmac
import time
import base64
import hashlib
import secrets


_PENDING: dict[str, dict] = {}

CODE_TTL = 300
TOKEN_TTL = 30 * 86400
_MAX_PENDING = 5000

CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
CODE_LEN = 8
CODE_RE = r"[0-9A-Za-z]{6,10}"

_SECRET: bytes = b""


def init_secret(config_key: str = "", data_dir: str = "data/airi_daily_check") -> None:
    global _SECRET
    if config_key:
        _SECRET = config_key.encode("utf-8")
        return
    key_path = os.path.join(data_dir, "web_token.key")
    try:
        with open(key_path, "rb") as f:
            _SECRET = f.read().strip()
        if _SECRET:
            return
    except OSError:
        pass
    _SECRET = secrets.token_hex(32).encode("ascii")
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(key_path, "wb") as f:
            f.write(_SECRET)
    except OSError:
        pass


def _gc_pending(now: float) -> None:
    expired = [c for c, v in _PENDING.items() if now - v["ts"] > CODE_TTL]
    for c in expired:
        _PENDING.pop(c, None)
    if len(_PENDING) > _MAX_PENDING:
        for c in sorted(_PENDING, key=lambda k: _PENDING[k]["ts"])[: len(_PENDING) - _MAX_PENDING]:
            _PENDING.pop(c, None)


def _gen() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))


def normalize_code(code: str) -> str:
    return str(code or "").strip().upper()


def new_code() -> str:
    now = time.time()
    _gc_pending(now)
    for _ in range(20):
        code = _gen()
        if code not in _PENDING:
            _PENDING[code] = {"qq": None, "nick": "", "ts": now}
            return code
    code = _gen()
    _PENDING[code] = {"qq": None, "nick": "", "ts": now}
    return code


def confirm_code(code: str, qq: str, nick: str) -> bool:
    code = normalize_code(code)
    rec = _PENDING.get(code)
    if rec is None:
        return False
    if time.time() - rec["ts"] > CODE_TTL:
        _PENDING.pop(code, None)
        return False
    rec["qq"] = str(qq)
    rec["nick"] = nick or str(qq)
    return True


def poll_code(code: str):
    code = normalize_code(code)
    rec = _PENDING.get(code)
    if rec is None:
        return None
    if time.time() - rec["ts"] > CODE_TTL:
        _PENDING.pop(code, None)
        return None
    if rec["qq"] is None:
        return None
    _PENDING.pop(code, None)
    return rec["qq"], rec["nick"]


def _sign(payload: str) -> str:
    sig = hmac.new(_SECRET, payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")


def issue_token(qq: str) -> str:
    expiry = int(time.time()) + TOKEN_TTL
    payload = f"{qq}.{expiry}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str):
    if not token:
        return None
    try:
        qq, expiry_s, sig = token.rsplit(".", 2)
    except ValueError:
        return None
    payload = f"{qq}.{expiry_s}"
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        if int(expiry_s) < time.time():
            return None
    except ValueError:
        return None
    return qq
