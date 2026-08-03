import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from plugins.airi_daily_check.roguelike.api import app as sekai_app
from utils import mailer

from . import auth
from .point_salad_api import router as point_salad_router


app = FastAPI(title="Airi Game Server", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(sekai_app.router)
app.include_router(point_salad_router)
_email_requests = {}


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
    key = f"{qq}:{_client_ip(request)}"
    if now - _email_requests.get(key, 0) < 60:
        raise HTTPException(status_code=429, detail="请稍后再获取验证码")
    code = auth.create_email_code(qq)
    result = await mailer.send_single(
        body.email,
        "AiriCore 网页登录验证码",
        f"你的 AiriCore 网页登录验证码是 {code}，5 分钟内有效。",
        tag="airi_game_server",
    )
    if result is not True:
        raise HTTPException(status_code=503, detail="验证码邮件暂时无法发送")
    _email_requests[key] = now
    return {"ok": True, "ttl": auth.EMAIL_CODE_TTL}


@app.post("/api/auth/email/confirm")
async def confirm_email_login(body: EmailConfirm):
    try:
        qq = auth.parse_qq_email(body.email)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if not auth.confirm_email_code(qq, body.code):
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    account = __import__("plugins.airi_daily_check.roguelike.store", fromlist=["ensure_account"]).ensure_account(qq)
    nick = account.get("web_nick") or qq
    return {"ok": True, "token": auth.issue_token(qq), "qq": qq, "nick": nick}


@app.get("/api/health")
async def health():
    return {"ok": True}
