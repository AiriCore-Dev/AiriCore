from nonebot import on_command
from nonebot.adapters import Message
from nonebot.internal.adapter import Bot, Event
from nonebot.params import CommandArg
from nonebot_plugin_alconna import Reply, UniMessage

from utils.credit import ChargeRejected
from ..billing import production_charge
from ..dialogue.interaction import _message_key, _receipt_ids
from ..runtime import logger, run_image, session_file
from .parser import parse_debate
from .state import DebateSessionStore


DEBATE_HELP = """用法：魔裁审问 立绘短码 -左/-右 文字
立绘短码、人物位置和正文支持乱序，以空白分隔。
-左 / -右 指人物所在侧，文字显示在另一侧。
每张图使用一个立绘；正文最多八行，可用实际换行、\\n 或 <br> 分行。
正文中的 \\\\n 保留为字面量，不会换行。
用 **文字** 标记原作粉色强调，可使用多处标记。
固定原作字号，长行请手动换行；参数字样可用引号保护。
示例：魔裁审问 #CFAMVMR9LZ -左 这就是**证据**。
制作收费10积分。回复生成图发送完整的魔裁鸭梨指令，可制作叠加图。"""
debate_handler = on_command("魔裁审问", block=True)
_SESSION_STORE = None


def _session_store():
    global _SESSION_STORE
    if _SESSION_STORE is None:
        _SESSION_STORE = DebateSessionStore(session_file("debate_sessions.json"))
    return _SESSION_STORE


async def resolve_debate_reply(bot, event, message):
    if message is None:
        return None
    reply = next((segment for segment in message if isinstance(segment, Reply)), None)
    if reply is None:
        return None
    return await _session_store().get_message(_message_key(bot, event, str(reply.id)))


@debate_handler.handle()
async def handle_debate(bot: Bot, event: Event, argument: Message = CommandArg()):
    from .rendering import render_debate

    text = argument.extract_plain_text().strip()
    if not text or text in {"-h", "--help", "帮助"}:
        await UniMessage.text(DEBATE_HELP).send(target=event, bot=bot)
        return
    try:
        request = parse_debate(text)
        payload = await run_image(render_debate, request)
        async with production_charge(event.get_user_id()):
            receipt = await UniMessage.image(raw=payload, mimetype="image/png").send(target=event, bot=bot)
    except (ValueError, OverflowError, ChargeRejected) as error:
        await UniMessage.text(str(error)).send(target=event, bot=bot)
        return
    try:
        message_ids = _receipt_ids(receipt)
        if not message_ids:
            raise ValueError("发送回执未提供消息编号")
        for message_id in message_ids:
            await _session_store().set_message(_message_key(bot, event, message_id), request)
    except (OSError, ValueError):
        logger.exception("审问图片已发送，但回复关联保存失败")
        await UniMessage.text("图片已生成，但回复关联未能保存，本图暂时无法叠加魔裁鸭梨。请联系管理员检查存储。").send(target=event, bot=bot)
