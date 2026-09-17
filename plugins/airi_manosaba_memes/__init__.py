import re

from nonebot import on_command, on_regex, require
from nonebot.internal.adapter import Bot, Event
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_htmlrender")

from nonebot_plugin_alconna import (
    Alconna,
    Args,
    Arparma,
    CommandMeta,
    OriginalUniMsg,
    UniMessage,
    on_alconna,
)

from .drawer import draw_anan, draw_trial
from .billing import production_charge
from .help import render_help
from utils.credit import ChargeRejected
from .runtime import logger, run_image
from .trial import TRIAL_HELP, parse_trial
from .sprite_editor.interaction import (
    FOLLOWUP_RE,
    SPRITE_HELP,
    handle_sprite,
    handle_sprite_followup,
)
from .dialogue.interaction import (
    handle_background,
    handle_background_followup,
    handle_dialogue,
)
from .utils import CHARACTER_NAMES
from .debate.interaction import handle_debate, resolve_debate_reply
from .debate.composition import render_debate_trial

CHARACTER_NAMES_TEXT = ", ".join(CHARACTER_NAMES)

usage = f"""
manohelp：查看图片帮助
制作收费 10 积分；立绘与背景选择表、翻页和后续编辑免费
安安说 [文本] [表情]
    表情可选：害羞, 生气, 病娇, 无语, 开心
魔裁鸭梨 角色名
【疑问/反驳/伪证/赞同/魔法:角色名】这是一个选项文本
    角色名与选项写在同一条消息中，每行一个选项，支持 1～6 个选项
    角色名可选：{CHARACTER_NAMES_TEXT}
    发送 魔裁鸭梨 -h 查看完整帮助
魔裁立绘 [角色名或立绘短码]
    从官方预设开始生成立绘，并通过回复消息精细调整
    发送 魔裁立绘 -h 查看完整帮助
魔裁背景 [场景/插图/特效/CG] [页码]
    免费查看官方背景与 CG，也可使用 @BGxxx 或 @CGxxx 直接查看
魔裁对话 @背景短码 [立绘短码] [*姓名] 正文
    最多三个立绘，生成对话图收费 10 积分
魔裁审问 立绘短码 -左/-右 文字
    参数可乱序，**文字** 表示粉色强调，最多八行
    回复审问图发送魔裁鸭梨，可生成半透明黑色底的叠加图
""".strip()

__plugin_meta__ = PluginMetadata(
    name="魔裁 Memes",
    description="生成「魔法少女的魔法审判」的表情包",
    usage=usage,
    type="application",
    homepage="https://github.com/zhaomaoniu/nonebot-plugin-manosaba-memes",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)

anan_says_handler = on_alconna(
    Alconna(
        "安安说",
        Args["text", str]["face", str, None],
        meta=CommandMeta(
            description="让安安说话的插件",
            usage="安安说 [文本] [表情]\n表情可选：害羞, 生气, 病娇, 无语, 开心",
            example="安安说 吾辈现在不想说话",
        ),
    ),
    aliases={"anan说", "anansays"},
    use_cmd_start=True,
)
trial_handler = on_command("魔裁鸭梨", block=True)
sprite_handler = on_alconna(
    Alconna(
        "魔裁立绘",
        Args["character", str, None],
        meta=CommandMeta(
            description="从官方预设创建并精细调整角色立绘",
            usage=SPRITE_HELP,
            example=(
                "魔裁立绘 梅露露\n"
                "P1\n"
                "魔裁立绘 #MLL001\n"
                "#MLL001 眼睛"
            ),
        ),
    ),
    use_cmd_start=True,
)
sprite_followup_handler = on_regex(
    FOLLOWUP_RE.pattern,
    flags=re.IGNORECASE,
    priority=12,
    block=False,
)

manohelp_handler = on_command("manohelp", block=True)


@manohelp_handler.handle()
async def handle_manohelp():
    try:
        payload = await render_help()
    except ValueError as error:
        await manohelp_handler.finish(str(error))
    except Exception:
        logger.exception("魔裁帮助图片渲染失败")
        await manohelp_handler.finish("魔裁帮助图片渲染失败，请稍后再试或联系管理员")
    await UniMessage.image(raw=payload, mimetype="image/jpeg").finish()


@anan_says_handler.handle()
async def handle_anan_says(event: Event, result: Arparma):
    user_result = result["text"]
    face = result["face"]
    text = user_result.replace("\\n", "\n")
    try:
        image_bytes = await run_image(draw_anan, text, face)
    except ValueError as error:
        await anan_says_handler.finish(str(error))
    try:
        async with production_charge(event.get_user_id()):
            await anan_says_handler.send(UniMessage.image(raw=image_bytes, mimetype="image/png"))
    except ChargeRejected as error:
        await anan_says_handler.finish(str(error))
    return


@trial_handler.handle()
async def handle_trial(bot: Bot, event: Event, argument: Message = CommandArg(), message: OriginalUniMsg = None):
    text = argument.extract_plain_text().strip()
    if not text or text in {"-h", "--help", "帮助"}:
        await trial_handler.finish(TRIAL_HELP)
    try:
        character, options = parse_trial(text)
        debate = await resolve_debate_reply(bot, event, message)
        if debate is None:
            image_bytes = await run_image(draw_trial, character, options)
        else:
            image_bytes = await run_image(render_debate_trial, debate, character, options)
    except (OverflowError, ValueError) as error:
        await trial_handler.finish(str(error))
    try:
        async with production_charge(event.get_user_id()):
            await trial_handler.send(await UniMessage.image(raw=image_bytes, mimetype="image/png").export(bot))
    except ChargeRejected as error:
        await trial_handler.finish(str(error))
    return


@sprite_handler.handle()
async def handle_sprite_entry(bot: Bot, event: Event, result: Arparma) -> None:
    try:
        await handle_sprite(bot, event, result)
    except (ChargeRejected, ValueError) as error:
        await sprite_handler.finish(str(error))


@sprite_followup_handler.handle()
async def handle_sprite_followup_entry(
    bot: Bot, event: Event, message: OriginalUniMsg
) -> None:
    try:
        await handle_sprite_followup(bot, event, message)
    except (ChargeRejected, ValueError) as error:
        await sprite_followup_handler.finish(str(error))
