import math
import re

from nonebot import on_command, on_regex
from nonebot.adapters import Message
from nonebot.internal.adapter import Bot, Event
from nonebot.params import CommandArg
from nonebot_plugin_alconna import OriginalUniMsg, Reply, UniMessage, get_target

from ..billing import production_charge
from ..runtime import run_image, session_file
from utils.credit import ChargeRejected
from .catalog import CATEGORIES, PAGE_SIZE, BackgroundCatalog, BackgroundEntry
from .parser import parse_dialogue
from .state import BackgroundPickerContext, BackgroundSessionStore


BACKGROUND_FOLLOWUP_RE = re.compile(r"^(?:B[1-9][0-9]{0,3}|上一页|下一页)$", re.IGNORECASE)
DIALOGUE_HELP = """用法：魔裁对话 @背景短码 [立绘短码...] [*姓名] 正文
背景必须指定一个，立绘最多三个并按出现顺序排列。
*none 隐藏姓名牌，*? 使用未知人物姓名牌。
正文中的参数字样请使用引号包裹或反斜线转义。"""
BACKGROUND_HELP = """用法：魔裁背景 [场景/插图/特效] [页码]
也可发送：魔裁背景 @背景短码
回复选择表发送 B编号、上一页 或 下一页。"""
HELP_ARGUMENTS = {"-h", "--help", "帮助"}

dialogue_handler = on_command("魔裁对话", block=True)
background_handler = on_command("魔裁背景", block=True)
background_followup_handler = on_regex(
    BACKGROUND_FOLLOWUP_RE.pattern,
    flags=re.IGNORECASE,
    priority=12,
    block=False,
)

_CATALOG = None
_SESSION_STORE = None


def _catalog() -> BackgroundCatalog:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = BackgroundCatalog()
    return _CATALOG


def _session_store() -> BackgroundSessionStore:
    global _SESSION_STORE
    if _SESSION_STORE is None:
        _SESSION_STORE = BackgroundSessionStore(
            session_file("background_sessions.json")
        )
    return _SESSION_STORE


def parse_background_command(text: str) -> tuple[str, str, int | None]:
    values = text.split()
    if not values:
        return "picker", "场景", 1
    if len(values) == 1 and values[0].startswith("@"):
        code = values[0].upper()
        if not re.fullmatch(r"@BG[0-9]{3}", code):
            raise ValueError(f"背景短码无效：{values[0]}")
        return "background", code, None
    if len(values) > 2:
        raise ValueError("用法：魔裁背景 [场景/插图/特效] [页码] 或 魔裁背景 @背景短码")
    category = "场景"
    category_seen = False
    page_text = None
    for value in values:
        if value in CATEGORIES:
            if category_seen:
                raise ValueError("只能指定一个背景分类")
            category = value
            category_seen = True
        elif value.isdecimal():
            if page_text is not None:
                raise ValueError("只能指定一个页码")
            page_text = value
        else:
            raise ValueError(f"背景参数无效：{value}")
    page = int(page_text or "1")
    if page < 1:
        raise ValueError("页码必须从 1 开始")
    return "picker", category, page


def background_choice(codes: list[str], command: str) -> str:
    match = re.fullmatch(r"B([1-9][0-9]{0,3})", command, re.IGNORECASE)
    if match is None:
        raise ValueError("请使用 B 加编号选择背景")
    index = int(match.group(1)) - 1
    if index >= len(codes):
        raise ValueError("这个编号不在选择表中")
    return codes[index]


def next_page(page: int, count: int, command: str) -> int:
    total_pages = max(1, math.ceil(count / PAGE_SIZE))
    delta = 1 if command == "下一页" else -1
    return min(max(page + delta, 1), total_pages)


def _target_key(bot: Bot, event: Event) -> str:
    target = get_target(event, bot)
    kind = "private" if target.private else "channel"
    return "|".join(
        (
            bot.adapter.get_name(),
            str(bot.self_id),
            kind,
            str(target.parent_id),
            str(target.id),
        )
    )


def _message_key(bot: Bot, event: Event, message_id: str) -> str:
    return f"{_target_key(bot, event)}|{message_id}"


def _receipt_ids(receipt: object) -> list[str]:
    replies = getattr(receipt, "get_reply", lambda: None)()
    if replies:
        return [str(reply.id) for reply in replies]
    return [
        str(value) for value in getattr(receipt, "msg_ids", []) if value is not None
    ]


async def _send_picker(
    bot: Bot,
    event: Event,
    category: str,
    page: int,
    entries: tuple[BackgroundEntry, ...],
) -> None:
    from .rendering import render_background_picker

    total_pages = max(1, math.ceil(len(entries) / PAGE_SIZE))
    bounded = min(max(page, 1), total_pages)
    offset = (bounded - 1) * PAGE_SIZE
    shown = entries[offset : offset + PAGE_SIZE]
    if not shown:
        await UniMessage.text(f"{category}分类暂无可用背景。").send(
            target=event, bot=bot
        )
        return
    image = await run_image(render_background_picker, shown, offset)
    last = offset + len(shown)
    caption = (
        f"{category}背景 {bounded}/{total_pages}\n"
        f"请回复 B{offset + 1}～B{last} 选择；回复 上一页 / 下一页 翻页。"
    )
    receipt = await UniMessage.image(raw=image, mimetype="image/png").text(
        f"\n{caption}"
    ).send(target=event, bot=bot)
    context = BackgroundPickerContext(
        category=category,
        page=bounded,
        codes=[entry.code for entry in entries],
    )
    for message_id in _receipt_ids(receipt):
        await _session_store().set_message(
            _message_key(bot, event, message_id), context
        )


async def _send_background(bot: Bot, event: Event, entry: BackgroundEntry) -> None:
    from .rendering import render_background

    image = await run_image(render_background, entry)
    await UniMessage.image(raw=image, mimetype="image/png").text(
        f"\n{entry.code} · {entry.name}"
    ).send(target=event, bot=bot)


async def _send_text(bot: Bot, event: Event, text: str) -> None:
    await UniMessage.text(text).send(target=event, bot=bot)


@dialogue_handler.handle()
async def handle_dialogue(
    bot: Bot, event: Event, argument: Message = CommandArg()
) -> None:
    from .rendering import render_dialogue

    text = argument.extract_plain_text().strip()
    if not text or text in HELP_ARGUMENTS:
        await _send_text(bot, event, DIALOGUE_HELP)
        return
    try:
        request = parse_dialogue(text)
        _catalog().get(request.background)
        image = await run_image(render_dialogue, request)
        async with production_charge(event.get_user_id()):
            await UniMessage.image(raw=image, mimetype="image/png").send(
                target=event, bot=bot
            )
    except KeyError:
        await _send_text(bot, event, "没有找到这个背景短码。")
    except (OverflowError, ValueError) as error:
        await _send_text(bot, event, str(error))
    except ChargeRejected as error:
        await _send_text(bot, event, str(error))


@background_handler.handle()
async def handle_background(
    bot: Bot, event: Event, argument: Message = CommandArg()
) -> None:
    text = argument.extract_plain_text().strip()
    if text in HELP_ARGUMENTS:
        await _send_text(bot, event, BACKGROUND_HELP)
        return
    try:
        kind, value, page = parse_background_command(text)
        if kind == "background":
            await _send_background(bot, event, _catalog().get(value))
            return
        await _send_picker(bot, event, value, page or 1, _catalog().entries(value))
    except KeyError:
        await _send_text(bot, event, "没有找到这个背景短码。")
    except ValueError as error:
        await _send_text(bot, event, str(error))


@background_followup_handler.handle()
async def handle_background_followup(
    bot: Bot, event: Event, message: OriginalUniMsg
) -> None:
    reply = next((segment for segment in message if isinstance(segment, Reply)), None)
    if reply is None:
        return
    context = await _session_store().get_message(
        _message_key(bot, event, str(reply.id))
    )
    if context is None:
        return
    command = event.get_message().extract_plain_text().strip()
    try:
        if command in {"上一页", "下一页"}:
            page = next_page(context.page, len(context.codes), command)
            if page == context.page:
                text = "已经是最后一页。" if command == "下一页" else "已经是第一页。"
                await UniMessage.text(text).send(target=event, bot=bot)
                return
            entries = tuple(_catalog().get(code) for code in context.codes)
            await _send_picker(bot, event, context.category, page, entries)
            return
        code = background_choice(context.codes, command)
        await _send_background(bot, event, _catalog().get(code))
    except KeyError:
        await UniMessage.text("背景目录已更新，这个旧选项暂时不可用。").send(
            target=event, bot=bot
        )
    except ValueError as error:
        await UniMessage.text(str(error)).send(target=event, bot=bot)
