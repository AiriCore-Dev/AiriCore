import asyncio
import base64
import html
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

from .asset_cache import get_source
from .output import add_watermark
from .runtime import run_sync


HELP_ROOT = Path(__file__).parent / "assets/help"
HELP_PATH = HELP_ROOT / "index.md"
HELP_CSS = HELP_ROOT / "style.css"
FONT_PATH = Path(__file__).parent / "assets/fonts/SourceHanSansSC-Bold.otf"
_render_lock = asyncio.Lock()


def build_help_html(path: Path = HELP_PATH) -> str:
    try:
        document = get_source(path).decode("utf-8-sig")
        css = get_source(HELP_CSS).decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError("魔裁帮助文档读取失败，请联系管理员") from error
    parser = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = parser.parse(document)
    pending = list(tokens)
    while pending:
        token = pending.pop()
        pending.extend(token.children or ())
        if token.type != "image":
            continue
        location = urlsplit(token.attrGet("src") or "")
        source = (path.parent / unquote(location.path)).resolve()
        if location.scheme or location.netloc or not source.is_relative_to(path.parent.resolve()):
            raise ValueError("帮助示例图片必须使用帮助目录内的相对路径")
        try:
            payload = get_source(source)
        except OSError as error:
            raise ValueError(f"帮助示例图片读取失败：{source.name}") from error
        mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        token.attrSet("src", f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}")
    body = parser.renderer.render(tokens, parser.options, {})
    css = css.replace("__HELP_FONT__", FONT_PATH.resolve().as_uri())
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>{css}</style><title>{html.escape("魔裁表情包帮助")}</title></head><body><main>{body}</main></body></html>'


async def render_help(path: Path = HELP_PATH) -> bytes:
    from nonebot_plugin_htmlrender import get_new_page

    async with _render_lock:
        document = await run_sync(build_help_html, path)
        async with get_new_page(device_scale_factor=1.5, viewport={"width": 1000, "height": 800}) as page:
            await page.goto(path.parent.resolve().as_uri() + "/")
            await page.set_content(document, wait_until="load")
            await page.evaluate("document.fonts.ready")
            await page.evaluate("Promise.all(Array.from(document.images, image => image.decode()))")
            payload = await page.screenshot(type="jpeg", full_page=True)
        return await run_sync(add_watermark, payload)
