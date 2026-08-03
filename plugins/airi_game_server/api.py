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
EMAIL_IP_COOLDOWN = 5 * 60
EMAIL_DAILY_LIMIT = 2


class EmailRequest(BaseModel):
    email: str


class EmailConfirm(BaseModel):
    email: str
    code: str


def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "") or "unknown"


@app.post("/api/auth/email/request")
async def request_email_login(body: EmailRequest, request: Request):
    try:
        qq = auth.parse_qq_email(body.email)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    now = time.time()
    client_ip = _client_ip(request)
    last_request = _email_ip_requests.get(client_ip)
    if last_request is not None and now - last_request < EMAIL_IP_COOLDOWN:
        raise HTTPException(status_code=429, detail="同一 IP 请 5 分钟后再进行邮箱认证")
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    recorded_day, attempts = _email_daily_attempts.get(qq, (day, 0))
    if recorded_day != day:
        attempts = 0
    if attempts >= EMAIL_DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="该邮箱今日登录次数已达上限，请明天再试")
    code = auth.create_email_code(qq)
    result = await mailer.send_single(
        body.email,
        "AiriCore 网页登录验证码",
        f"你的 AiriCore 网页登录验证码是 {code}，5 分钟内有效。",
        tag="airi_game_server",
    )
    if result is not True:
        raise HTTPException(status_code=503, detail="验证码邮件暂时无法发送")
    _email_ip_requests[client_ip] = now
    _email_daily_attempts[qq] = (day, attempts + 1)
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
