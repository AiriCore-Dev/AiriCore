import os
import ssl
import mimetypes
from aiohttp import web
from nonebot.log import logger

from ..base import state
from ..base.helpers import verify_token

FONT = "'Segoe UI', Arial, sans-serif"

_STYLE = f"""
body{{margin:0;padding:0;min-height:100vh;background:linear-gradient(135deg,#fff0f7 0%,#fde8f0 100%);
  display:flex;align-items:center;justify-content:center;font-family:{FONT};}}
.card{{background:#fff;border-radius:20px;box-shadow:0 8px 32px rgba(232,93,154,.15);
  padding:48px 56px;max-width:440px;width:90%;text-align:center;}}
.logo{{width:64px;height:64px;border-radius:50%;margin-bottom:20px;}}
.title{{font-size:24px;font-weight:700;color:#2b2b33;margin:0 0 10px 0;}}
.subtitle{{font-size:15px;color:#55555f;line-height:1.7;margin:0 0 28px 0;}}
.btn{{display:inline-block;padding:13px 32px;border-radius:999px;font-size:15px;font-weight:700;
  cursor:pointer;border:none;text-decoration:none;transition:opacity .2s;}}
.btn:hover{{opacity:.85;}}
.btn-primary{{background:linear-gradient(135deg,#ff7fb3,#e85d9a);color:#fff;}}
.btn-ghost{{background:#fde8f0;color:#e85d9a;margin-left:12px;}}
.tag{{display:inline-block;padding:6px 18px;border-radius:999px;font-size:13px;font-weight:700;margin-bottom:18px;}}
.tag-done{{background:#e6f7f0;color:#1fae7a;}}
.tag-warn{{background:#fde8f0;color:#e85d9a;}}
.hint{{margin-top:18px;font-size:12px;color:#b0b0ba;line-height:1.6;}}
@media(prefers-color-scheme:dark){{
  body{{background:linear-gradient(135deg,#1a1a22,#26222e);}}
  .card{{background:#26262e;box-shadow:0 8px 32px rgba(0,0,0,.3);}}
  .title{{color:#f0f0f5;}}
  .subtitle{{color:#a0a0b0;}}
  .btn-ghost{{background:#3e2e38;}}
  .hint{{color:#6a6a7a;}}
}}
"""


def _page(tag_text, tag_class, title, subtitle, buttons_html, hint=""):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title} - Airi</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="card">
<img class="logo" src="https://www.airi.asia/assets/images/icon.avif" alt="Airi" />
<div class="tag {tag_class}">{tag_text}</div>
<h1 class="title">{title}</h1>
<p class="subtitle">{subtitle}</p>
{buttons_html}
{"<p class='hint'>" + hint + "</p>" if hint else ""}
</div>
</body>
</html>"""


def _page_invalid():
    return _page(
        "链接无效", "tag-warn",
        "链接已失效",
        "此退订链接无效或已过期，请从邮件中重新点击链接。",
        "",
        "如有疑问请联系 airicore@saki.ln.cn",
    )


def _page_unsub_confirm(token, qq):
    return _page(
        "确认退订", "tag-warn",
        "确认退订邮件推送",
        f"您（QQ：{qq}）将不再收到来自 Airi 的营销邮件推送。<br />此操作可随时撤销。",
        f'<a class="btn btn-primary" href="/api/unsubscribe?token={token}">确认退订</a>'
        f'<a class="btn btn-ghost" href="javascript:history.back()">取消</a>',
    )


def _page_unsub_done(token, qq):
    return _page(
        "已退订", "tag-done",
        "退订成功",
        f"您（QQ：{qq}）已成功退订，此后将不再收到营销邮件。",
        f'<a class="btn btn-ghost" href="/resubscribe?token={token}">撤销退订</a>',
        "退订后仍可能收到与账户相关的重要通知邮件",
    )


def _page_resub_confirm(token, qq):
    return _page(
        "撤销退订", "tag-done",
        "重新订阅邮件推送",
        f"您（QQ：{qq}）将重新开始接收来自 Airi 的营销邮件推送。",
        f'<a class="btn btn-primary" href="/api/resubscribe?token={token}">确认订阅</a>'
        f'<a class="btn btn-ghost" href="javascript:history.back()">取消</a>',
    )


def _page_resub_done(qq):
    return _page(
        "已订阅", "tag-done",
        "重新订阅成功",
        f"您（QQ：{qq}）已成功重新订阅，后续将继续收到 Airi 的邮件推送。",
        "",
    )


def _page_already_unsub(token, qq):
    return _page(
        "已退订", "tag-warn",
        "您已在退订名单中",
        f"QQ {qq} 已经是退订状态，无需重复操作。",
        f'<a class="btn btn-ghost" href="/resubscribe?token={token}">撤销退订</a>',
    )


async def handle_unsubscribe(request):
    token = request.rel_url.query.get("token", "")
    qq = verify_token(token)
    if not qq:
        return web.Response(text=_page_invalid(), content_type="text/html", charset="utf-8")
    html = _page_unsub_confirm(token, qq)
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def handle_api_unsubscribe(request):
    token = request.rel_url.query.get("token", "")
    qq = verify_token(token)
    if not qq:
        return web.Response(text=_page_invalid(), content_type="text/html", charset="utf-8")
    unsub_list = state.data.setdefault("unsubscribed", [])
    if qq not in unsub_list:
        unsub_list.append(qq)
        from ..base.persistence import save_data
        import asyncio
        asyncio.create_task(save_data())
        html = _page_unsub_done(token, qq)
    else:
        html = _page_already_unsub(token, qq)
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def handle_resubscribe(request):
    token = request.rel_url.query.get("token", "")
    qq = verify_token(token)
    if not qq:
        return web.Response(text=_page_invalid(), content_type="text/html", charset="utf-8")
    html = _page_resub_confirm(token, qq)
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def handle_api_resubscribe(request):
    token = request.rel_url.query.get("token", "")
    qq = verify_token(token)
    if not qq:
        return web.Response(text=_page_invalid(), content_type="text/html", charset="utf-8")
    unsub_list = state.data.setdefault("unsubscribed", [])
    if qq in unsub_list:
        unsub_list.remove(qq)
        from ..base.persistence import save_data
        import asyncio
        asyncio.create_task(save_data())
    html = _page_resub_done(qq)
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def handle_static_posts(request):
    article = request.match_info["article"]
    filename = request.match_info["filename"]
    safe_article = os.path.basename(article)
    safe_file = os.path.basename(filename)
    path = os.path.join(state.POSTS_DIR, safe_article, safe_file)
    if not os.path.isfile(path):
        return web.Response(status=404, text="Not Found")
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "application/octet-stream"
    with open(path, "rb") as f:
        data = f.read()
    return web.Response(body=data, content_type=mime)


async def start_server():
    app = web.Application()
    app.router.add_get("/unsubscribe", handle_unsubscribe)
    app.router.add_get("/api/unsubscribe", handle_api_unsubscribe)
    app.router.add_get("/resubscribe", handle_resubscribe)
    app.router.add_get("/api/resubscribe", handle_api_resubscribe)
    app.router.add_get("/static/posts/{article}/{filename}", handle_static_posts)

    ssl_ctx = None
    if os.path.isfile(state.SSL_CERT) and os.path.isfile(state.SSL_KEY):
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(state.SSL_CERT, state.SSL_KEY)
    else:
        logger.warning("airi_market: SSL cert not found, running without HTTPS")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", state.market_port, ssl_context=ssl_ctx)
    try:
        await site.start()
        state._web_runner = runner
        proto = "https" if ssl_ctx else "http"
        logger.info(f"airi_market web server started at {proto}://0.0.0.0:{state.market_port}")
    except Exception as e:
        logger.error(f"airi_market web server failed to start: {e}")
        await runner.cleanup()
