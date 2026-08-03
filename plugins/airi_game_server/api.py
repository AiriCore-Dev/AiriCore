import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from utils import mailer

from . import accounts, auth
from .point_salad_api import router as point_salad_router
from .sekai_api import router as sekai_router


app = FastAPI(title="Airi Game Server", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(sekai_router)
app.include_router(point_salad_router)
_email_ip_requests = {}
_email_daily_attempts = {}
_email_sending = set()
EMAIL_IP_COOLDOWN = 5 * 60
EMAIL_DAILY_LIMIT = 2


class EmailRequest(BaseModel):
    email: str


class EmailConfirm(BaseModel):
    email: str
    code: str


def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "") or "unknown"


def _prune_email_limits(now: float, day: str):
    stale_ips = [
        client_ip
        for client_ip, requested_at in _email_ip_requests.items()
        if now - requested_at >= EMAIL_IP_COOLDOWN
    ]
    for client_ip in stale_ips:
        _email_ip_requests.pop(client_ip, None)
    stale_accounts = [
        qq
        for qq, (recorded_day, _) in _email_daily_attempts.items()
        if recorded_day != day
    ]
    for qq in stale_accounts:
        _email_daily_attempts.pop(qq, None)


def _rollback_email_limit(client_ip, requested_at, qq, previous, reserved):
    if _email_ip_requests.get(client_ip) == requested_at:
        _email_ip_requests.pop(client_ip, None)
    if _email_daily_attempts.get(qq) == reserved:
        if previous is None:
            _email_daily_attempts.pop(qq, None)
        else:
            _email_daily_attempts[qq] = previous


@app.post("/api/auth/email/request")
async def request_email_login(body: EmailRequest, request: Request):
    try:
        qq = auth.parse_qq_email(body.email)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    now = time.time()
    client_ip = _client_ip(request)
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    _prune_email_limits(now, day)
    last_request = _email_ip_requests.get(client_ip)
    if last_request is not None and now - last_request < EMAIL_IP_COOLDOWN:
        raise HTTPException(status_code=429, detail="同一 IP 请 5 分钟后再进行邮箱认证")
    previous = _email_daily_attempts.get(qq)
    recorded_day, attempts = previous or (day, 0)
    if recorded_day != day:
        attempts = 0
    if attempts >= EMAIL_DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="该邮箱今日登录次数已达上限，请明天再试")
    if qq in _email_sending:
        raise HTTPException(status_code=429, detail="该邮箱的验证码正在发送，请稍后再试")
    code = auth.create_email_code(qq)
    reserved = (day, attempts + 1)
    _email_ip_requests[client_ip] = now
    _email_daily_attempts[qq] = reserved
    _email_sending.add(qq)
    try:
        result = await mailer.send_single(
            body.email,
            "AiriCore 网页登录验证码",
            f"你的 AiriCore 网页登录验证码是 {code}，5 分钟内有效。",
            tag="airi_game_server",
        )
    except Exception:
        auth.discard_email_code(qq)
        _rollback_email_limit(client_ip, now, qq, previous, reserved)
        raise
    finally:
        _email_sending.discard(qq)
    if result is not True:
        auth.discard_email_code(qq)
        _rollback_email_limit(client_ip, now, qq, previous, reserved)
        raise HTTPException(status_code=503, detail="验证码邮件暂时无法发送")
    return {"ok": True, "ttl": auth.EMAIL_CODE_TTL}


@app.post("/api/auth/email/confirm")
async def confirm_email_login(body: EmailConfirm):
    try:
        qq = auth.parse_qq_email(body.email)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if not auth.confirm_email_code(qq, body.code):
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    account = accounts.ensure_account(qq)
    nick = account.get("web_nick") or qq
    return {"ok": True, "token": auth.issue_token(qq), "qq": qq, "nick": nick}
