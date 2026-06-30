"""SEKAI roguelike web subsystem (imported by the parent plugin).

Adds:
  * a bot command "绑定网页 <code>" that links a web bind-code to the sender's
    real QQ number (the web then polls and receives a session token);
  * a FastAPI server on its own port (default 22319) exposing the credit /
    score / leaderboard API consumed by the web client.

Config (nonebot .env / driver.config), all optional:
  web_token_key   : str  — HMAC secret for session tokens (else random+persisted)
  web_api_host    : str  — bind host (default "0.0.0.0")
  web_api_port    : int  — bind port (default 22319)
  web_ssl_keyfile : str  — TLS 私钥路径 (default "./ssl/privkey.key")
  web_ssl_certfile: str  — TLS 证书链路径 (default "./ssl/fullchain.pem")
"""

import re
import os
import asyncio

import nonebot
from nonebot import get_driver, on_regex
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent

from . import auth, store
from .api import app as api_app

driver = get_driver()

# 复用父插件的会话解析（群聊里取真实发送者QQ）。父模块在本模块被 import 时已就绪。
import sys
_parent = sys.modules.get(__package__.rsplit(".", 1)[0]) if "." in __package__ else None


def _parse_user_id(ev: MessageEvent) -> str:
    if _parent and hasattr(_parent, "parse_session"):
        uid, _gid = _parent.parse_session(ev)
        return uid
    return str(ev.get_user_id())


# --- bind-code command ------------------------------------------------------
bind_web = on_regex(r"^登录网页\s*\d{4,8}$", priority=10, block=True)


@bind_web.handle()
async def _(bot: Bot, ev: MessageEvent):
    code = re.search(r"\d{4,8}", str(ev.get_plaintext())).group()
    user_id = _parse_user_id(ev)
    nick = ev.sender.card or ev.sender.nickname or user_id
    if auth.confirm_code(code, user_id, nick):
        store.ensure_account(user_id)  # 确保有账户（与签到等价的新号）
        acc = store.get_account(user_id)
        if acc is not None:
            acc["web_nick"] = nick
        await bind_web.finish(
            f"✅ 登录成功！\n欢迎你，{nick}\n现在可以回到网页开始你的SEKAI之旅啦～",
            reply_message=True,
        )
    else:
        await bind_web.finish(
            "❌ 绑定失败：验证码无效或已过期\n请回到网页点击登录重新获取验证码。",
            reply_message=True,
        )


# --- API server -------------------------------------------------------------
_server_task = None


@driver.on_startup
async def _start_api():
    global _server_task
    import uvicorn

    config = driver.config
    auth.init_secret(getattr(config, "web_token_key", ""))
    host = getattr(config, "web_api_host", "0.0.0.0")
    port = int(getattr(config, "web_api_port", 22319))
    ssl_keyfile = getattr(config, "web_ssl_keyfile", "./ssl/privkey.key")
    ssl_certfile = getattr(config, "web_ssl_certfile", "./ssl/fullchain.pem")

    # 仅当证书文件存在时启用 HTTPS，否则退化为 HTTP（避免缺证书时启动崩溃）。
    use_tls = bool(ssl_keyfile) and bool(ssl_certfile) \
        and os.path.isfile(ssl_keyfile) and os.path.isfile(ssl_certfile)

    kwargs = dict(host=host, port=port, log_level="warning", access_log=False)
    if use_tls:
        kwargs["ssl_keyfile"] = ssl_keyfile
        kwargs["ssl_certfile"] = ssl_certfile

    uconf = uvicorn.Config(api_app, **kwargs)
    server = uvicorn.Server(uconf)
    # uvicorn 默认会装信号处理器，与 nonebot 主进程冲突，禁用之。
    server.install_signal_handlers = lambda: None
    _server_task = asyncio.create_task(server.serve())
    scheme = "https" if use_tls else "http"
    logger.info(f"[SEKAI] web API listening on {scheme}://{host}:{port}"
                + ("" if use_tls else "  (⚠️ 未找到证书，已退化为 HTTP)"))


@driver.on_shutdown
async def _stop_api():
    global _server_task
    if _server_task and not _server_task.done():
        _server_task.cancel()
