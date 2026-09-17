import io
import math
import re

import aiohttp
from nonebot import on_command, on_regex
from nonebot.adapters import Message
from nonebot.internal.adapter import Bot, Event
from nonebot.params import CommandArg
from nonebot_plugin_alconna import Image as UniImage
from nonebot_plugin_alconna import OriginalUniMsg, Reply, UniMessage

from utils.credit import ChargeRejected
from utils.network import download_public_bytes
from ..billing import production_charge
from ..dialogue.interaction import HELP_ARGUMENTS, _message_key, _receipt_ids, _send_text
from ..dialogue.state import BackgroundPickerContext, BackgroundSessionStore
from ..runtime import run_image, session_file
from .catalog import PAGE_SIZE, ItemCatalog
from .parser import ITEM_RE, parse_evidence


EVIDENCE_HELP = '''用法：魔裁证物 %WP物品短码 [*名称 描述]
仅输入短码时，使用原游戏最新版本的中文证物名称和描述，长文自动缩小字号。
没有原版文案的物品需手动填写 *名称 描述。
也可在同一条消息中发送一张图片，用图片代替短码。
例如：魔裁证物 %WP001 *神秘零件 现场发现的机械零件。
短码、图片、*名称和描述可乱序，文字参数用空白分隔。
带空格的名称可写成 *"证物 名称"。
自定义描述支持实际换行、\\n 或 <br>，最多十二行；\\\\n 保留为字面量。
描述中的参数字样可用引号或反斜线保护。
图片最大 10 MB、2000 万像素，动图使用第一帧。
制作收费 10 积分；使用 魔裁物品 免费查看物品短码。'''
ITEM_HELP = '''用法：魔裁物品 [页码或%WP物品短码]
例如：魔裁物品 2 或 魔裁物品 %WP001
每页最多 25 个物品，短码格式为 %WPxxx（三位数字）。
回复选择表发送 W编号、上一页 或 下一页，编号跨页连续。
物品选择表、翻页和查看大图免费。'''
FOLLOWUP_RE = re.compile(r'^(?:W[1-9][0-9]{0,3}|上一页|下一页)$', re.IGNORECASE)
evidence_handler = on_command('魔裁证物', block=True)
item_handler = on_command('魔裁物品', block=True)
item_followup_handler = on_regex(FOLLOWUP_RE.pattern, flags=re.IGNORECASE, priority=12, block=False)
_CATALOG = None
_SESSION_STORE = None


def _catalog() -> ItemCatalog:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = ItemCatalog()
    return _CATALOG


def _session_store() -> BackgroundSessionStore:
    global _SESSION_STORE
    if _SESSION_STORE is None:
        _SESSION_STORE = BackgroundSessionStore(session_file('item_sessions.json'))
    return _SESSION_STORE


def parse_item_command(text: str) -> tuple[str, str | int]:
    value = text.strip()
    if not value:
        return 'picker', 1
    if ITEM_RE.fullmatch(value):
        return 'item', value.upper()
    if re.fullmatch(r'[1-9][0-9]{0,5}', value):
        return 'picker', int(value)
    raise ValueError('请输入从 1 开始的页码或 %WPxxx 物品短码')


def item_choice(codes: list[str], command: str) -> str:
    match = re.fullmatch(r'W([1-9][0-9]{0,3})', command, re.IGNORECASE)
    if match is None:
        raise ValueError('请使用 W 加编号选择物品')
    index = int(match.group(1)) - 1
    if index >= len(codes):
        raise ValueError('这个编号不在选择表中')
    return codes[index]


async def image_bytes(image: UniImage) -> bytes:
    from .rendering import MAX_IMAGE_BYTES

    raw = image.raw
    if isinstance(raw, io.BytesIO):
        raw = raw.getvalue()
    if isinstance(raw, bytes):
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError('物品图片不能为空或超过 10 MB')
        return raw
    if image.url:
        try:
            return await download_public_bytes(image.url, max_bytes=MAX_IMAGE_BYTES, timeout=20)
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError) as error:
            raise ValueError('物品图片下载失败，请重新发送不超过 10 MB 的图片') from error
    raise ValueError('无法读取这张物品图片，请重新发送')


@evidence_handler.handle()
async def handle_evidence(bot: Bot, event: Event, message: OriginalUniMsg, argument: Message = CommandArg()) -> None:
    from .rendering import render_evidence

    text = argument.extract_plain_text().strip()
    if not text or text in HELP_ARGUMENTS:
        await _send_text(bot, event, EVIDENCE_HELP)
        return
    images = [segment for segment in message if isinstance(segment, UniImage)]
    try:
        request = parse_evidence(text, image_count=len(images))
        if request.item is not None:
            _catalog().get(request.item)
        source = await image_bytes(images[0]) if images else None
        payload = await run_image(render_evidence, request, source)
        async with production_charge(event.get_user_id()):
            await UniMessage.image(raw=payload, mimetype='image/png').send(target=event, bot=bot)
    except KeyError:
        await _send_text(bot, event, '没有找到这个物品短码。')
    except (ValueError, OverflowError, ChargeRejected) as error:
        await _send_text(bot, event, str(error))


async def _send_picker(bot: Bot, event: Event, page: int, entries) -> None:
    from .rendering import render_item_picker

    total = max(1, math.ceil(len(entries) / PAGE_SIZE))
    bounded = min(max(page, 1), total)
    start = (bounded - 1) * PAGE_SIZE
    shown = entries[start:start + PAGE_SIZE]
    if not shown:
        await _send_text(bot, event, '暂无可用物品。')
        return
    payload = await run_image(render_item_picker, shown, start)
    caption = f'物品 {bounded}/{total}\n请回复 W{start + 1}～W{start + len(shown)} 选择；回复 上一页 / 下一页 翻页。'
    receipt = await UniMessage.image(raw=payload, mimetype='image/png').text('\n' + caption).send(target=event, bot=bot)
    context = BackgroundPickerContext(category='物品', page=bounded, codes=[entry.code for entry in entries])
    for message_id in _receipt_ids(receipt):
        await _session_store().set_message(_message_key(bot, event, message_id), context)


async def _send_item(bot: Bot, event: Event, entry) -> None:
    from .rendering import render_item

    payload = await run_image(render_item, entry)
    await UniMessage.image(raw=payload, mimetype='image/png').text(f'\n{entry.code} · {entry.name}').send(target=event, bot=bot)


@item_handler.handle()
async def handle_item(bot: Bot, event: Event, argument: Message = CommandArg()) -> None:
    text = argument.extract_plain_text().strip()
    if text in HELP_ARGUMENTS:
        await _send_text(bot, event, ITEM_HELP)
        return
    try:
        kind, value = parse_item_command(text)
        if kind == 'item':
            await _send_item(bot, event, _catalog().get(value))
        else:
            await _send_picker(bot, event, value, _catalog().entries())
    except KeyError:
        await _send_text(bot, event, '没有找到这个物品短码。')
    except ValueError as error:
        await _send_text(bot, event, str(error))


@item_followup_handler.handle()
async def handle_item_followup(bot: Bot, event: Event, message: OriginalUniMsg) -> None:
    reply = next((segment for segment in message if isinstance(segment, Reply)), None)
    if reply is None:
        return
    context = await _session_store().get_message(_message_key(bot, event, str(reply.id)))
    if context is None or context.category != '物品':
        return
    command = event.get_message().extract_plain_text().strip()
    try:
        if command in {'上一页', '下一页'}:
            total = max(1, math.ceil(len(context.codes) / PAGE_SIZE))
            page = min(max(context.page + (1 if command == '下一页' else -1), 1), total)
            if page == context.page:
                await _send_text(bot, event, '已经是最后一页。' if command == '下一页' else '已经是第一页。')
                return
            entries = tuple(_catalog().get(code) for code in context.codes)
            await _send_picker(bot, event, page, entries)
        else:
            await _send_item(bot, event, _catalog().get(item_choice(context.codes, command)))
    except KeyError:
        await _send_text(bot, event, '物品目录已更新，这个旧选项暂时不可用。')
    except ValueError as error:
        await _send_text(bot, event, str(error))
