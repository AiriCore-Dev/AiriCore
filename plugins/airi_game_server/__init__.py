import asyncio
import os
import re

from nonebot import get_driver, logger, on_regex
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.plugin import PluginMetadata

from . import auth
from .api import app


__plugin_meta__ = PluginMetadata(
    name="Airi 游戏服务器",
    description="SEKAI 与得分沙拉的网页 API 服务",
    usage="网页端使用验证码登录",
    extra={"author": "AiriCore Dev.", "version": "1.0.0"},
)

driver = get_driver()
bind_web = on_regex(rf"^登录网页\s*{auth.CODE_RE}$", priority=10, block=True)
_server_task = None


@bind_web.handle()
async def _(bot: Bot, ev: MessageEvent):
    match = re.search(auth.CODE_RE, ev.get_plaintext().replace("登录网页", "", 1))
    if match is None:
        await bind_web.finish("验证码格式不对，请回到网页重新获取。", reply_message=True)
    qq = str(ev.get_user_id())
    nick = ev.sender.card or ev.sender.nickname or qq
    if auth.confirm_bot_code(match.group(), qq, nick):
        auth.set_nick(qq, nick)
        await bind_web.finish("登录成功，请回到网页继续操作。", reply_message=True)
    await bind_web.finish("绑定失败，验证码无效或已过期。", reply_message=True)


@driver.on_startup
async def _start_server():
    global _server_task
    import uvicorn

    config = driver.config
    auth.init_secret(getattr(config, "web_token_key", ""))
    host = str(getattr(config, "web_api_host", "") or "").strip()
    keyfile = str(getattr(config, "web_ssl_keyfile", "") or "")
    certfile = str(getattr(config, "web_ssl_certfile", "") or "")
    use_tls = bool(keyfile and certfile and os.path.isfile(keyfile) and os.path.isfile(certfile))
    if not host:
        host = "0.0.0.0" if use_tls else "127.0.0.1"
    if host not in {"127.0.0.1", "localhost", "::1"} and not use_tls:
        logger.error("[游戏服务器] 公网 API 缺少 TLS 证书，已拒绝启动")
        return
    kwargs = {"host": host, "port": int(getattr(config, "web_api_port", 22319)), "log_level": "warning", "access_log": False}
    if use_tls:
        kwargs.update({"ssl_keyfile": keyfile, "ssl_certfile": certfile})
    server = uvicorn.Server(uvicorn.Config(app, **kwargs))
    server.install_signal_handlers = lambda: None
    _server_task = asyncio.create_task(server.serve())
    logger.info(f"[游戏服务器] API 已监听 {('https' if use_tls else 'http')}://{host}:{kwargs['port']}")


@driver.on_shutdown
async def _stop_server():
    if _server_task is not None and not _server_task.done():
        _server_task.cancel()
