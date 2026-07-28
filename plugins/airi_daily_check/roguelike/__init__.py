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

import sys
_parent = sys.modules.get(__package__.rsplit(".", 1)[0]) if "." in __package__ else None


def _parse_user_id(ev: MessageEvent) -> str:
    if _parent and hasattr(_parent, "parse_session"):
        uid, _gid = _parent.parse_session(ev)
        return uid
    return str(ev.get_user_id())


bind_web = on_regex(rf"^登录网页\s*{auth.CODE_RE}$", priority=10, block=True)


@bind_web.handle()
async def _(bot: Bot, ev: MessageEvent):
    m = re.search(auth.CODE_RE, str(ev.get_plaintext()).replace("登录网页", "", 1))
    if m is None:
        await bind_web.finish("验证码格式不对，请回到网页重新获取。", reply_message=True)
    code = m.group()
    user_id = _parse_user_id(ev)
    nick = ev.sender.card or ev.sender.nickname or user_id
    if auth.confirm_code(code, user_id, nick):
        store.ensure_account(user_id)
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


_server_task = None


@driver.on_startup
async def _start_api():
    global _server_task
    import uvicorn

    config = driver.config
    auth.init_secret(getattr(config, "web_token_key", ""))
    port = int(getattr(config, "web_api_port", 22319))
    ssl_keyfile = getattr(config, "web_ssl_keyfile", "./utils/ssl/privkey.key")
    ssl_certfile = getattr(config, "web_ssl_certfile", "./utils/ssl/fullchain.pem")
    allow_plain = bool(getattr(config, "web_allow_insecure_http", False))

    use_tls = bool(ssl_keyfile) and bool(ssl_certfile) \
        and os.path.isfile(ssl_keyfile) and os.path.isfile(ssl_certfile)

    host = str(getattr(config, "web_api_host", "") or "").strip()
    if not host:
        host = "0.0.0.0" if use_tls else "127.0.0.1"

    is_public = host not in ("127.0.0.1", "localhost", "::1")
    if not use_tls and is_public and not allow_plain:
        logger.error(
            f"[SEKAI] 未找到 TLS 证书而监听地址是 {host}，为避免 token 明文外泄已拒绝启动。"
            " 请配置 web_ssl_keyfile / web_ssl_certfile，"
            " 或把 web_api_host 改为 127.0.0.1，"
            " 或显式设置 web_allow_insecure_http = true。"
        )
        return

    kwargs = dict(host=host, port=port, log_level="warning", access_log=False)
    if use_tls:
        kwargs["ssl_keyfile"] = ssl_keyfile
        kwargs["ssl_certfile"] = ssl_certfile

    uconf = uvicorn.Config(api_app, **kwargs)
    server = uvicorn.Server(uconf)
    server.install_signal_handlers = lambda: None
    _server_task = asyncio.create_task(server.serve())
    scheme = "https" if use_tls else "http"
    logger.info(f"[SEKAI] web API listening on {scheme}://{host}:{port}"
                + ("" if use_tls else "  (未找到证书，已退化为 HTTP)"))


@driver.on_shutdown
async def _stop_api():
    global _server_task
    if _server_task and not _server_task.done():
        _server_task.cancel()
