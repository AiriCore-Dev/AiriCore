"""Web authentication for the SEKAI roguelike: bind-code flow + session tokens.

Why a bind code instead of QQ互联 OAuth?
    Official QQ Connect only returns an opaque `openid`, never the raw QQ number.
    The bot keys every account by the real QQ number, so we let the web mint a
    short one-time code; the user sends "绑定网页 <code>" to the bot, which knows
    the real QQ number from the message event and marks the code as bound.
    The web then polls and receives a signed session token.

Tokens are HMAC-SHA256 signed: "<qq>.<expiry>.<sig>" — stateless, no server
session store needed. The signing secret is taken from the driver config
(`web_token_key`); if absent we persist a random key under the data dir.
"""

import os
import hmac
import time
import base64
import hashlib
import secrets


# --- bind-code pool ---------------------------------------------------------
# code -> {"qq": str|None, "nick": str, "ts": float}
#   qq is None until the user confirms via the bot; then it holds the QQ number.
_PENDING: dict[str, dict] = {}

CODE_TTL = 300          # 绑定码有效期（秒）
TOKEN_TTL = 30 * 86400  # 会话token有效期（秒）
_MAX_PENDING = 5000     # 防内存膨胀的硬上限

_SECRET: bytes = b""


# --- signing secret ---------------------------------------------------------
def init_secret(config_key: str = "", data_dir: str = "data/airi_daily_check") -> None:
    """Resolve the token signing secret once at startup."""
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
        pass  # 退化为进程内临时密钥（重启后旧token失效）


def _gc_pending(now: float) -> None:
    expired = [c for c, v in _PENDING.items() if now - v["ts"] > CODE_TTL]
    for c in expired:
        _PENDING.pop(c, None)
    # 极端情况下仍超限：丢弃最旧的
    if len(_PENDING) > _MAX_PENDING:
        for c in sorted(_PENDING, key=lambda k: _PENDING[k]["ts"])[: len(_PENDING) - _MAX_PENDING]:
            _PENDING.pop(c, None)


# --- bind-code lifecycle ----------------------------------------------------
def new_code() -> str:
    """Mint a fresh 6-digit bind code (web side)."""
    now = time.time()
    _gc_pending(now)
    for _ in range(20):
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        if code not in _PENDING:
            _PENDING[code] = {"qq": None, "nick": "", "ts": now}
            return code
    # 退化：极小概率全冲突，直接覆盖
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    _PENDING[code] = {"qq": None, "nick": "", "ts": now}
    return code


def confirm_code(code: str, qq: str, nick: str) -> bool:
    """Bot side: mark a code as bound to a real QQ number. Returns success."""
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
    """Web side: returns (qq, nick) once bound, else None. One-time consume."""
    rec = _PENDING.get(code)
    if rec is None:
        return None
    if time.time() - rec["ts"] > CODE_TTL:
        _PENDING.pop(code, None)
        return None
    if rec["qq"] is None:
        return None
    _PENDING.pop(code, None)  # consume
    return rec["qq"], rec["nick"]


# --- session tokens ---------------------------------------------------------
def _sign(payload: str) -> str:
    sig = hmac.new(_SECRET, payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")


def issue_token(qq: str) -> str:
    expiry = int(time.time()) + TOKEN_TTL
    payload = f"{qq}.{expiry}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str):
    """Return the QQ number if the token is valid & unexpired, else None."""
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
