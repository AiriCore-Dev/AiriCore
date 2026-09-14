import re
from collections import defaultdict
from pathlib import Path

from nonebot import on_command, on_regex, require
from nonebot.internal.adapter import Bot, Event
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")

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
from utils.cache import get_b64, register_asset_group
from utils.credit import ChargeRejected
from .runtime import run_sync
from .models import Option
from .sprite_editor.interaction import (
    FOLLOWUP_RE,
    SPRITE_HELP,
    handle_sprite,
    handle_sprite_followup,
)
from .utils import CHARACTER_NAMES, get_character, get_statement

CHARACTER_NAMES_TEXT = ", ".join(CHARACTER_NAMES)

usage = f"""
manohelp：查看图片帮助
制作收费 10 积分；立绘选择表、翻页和后续编辑免费
安安说 [文本] [表情]
    表情可选：害羞, 生气, 病娇, 无语, 开心
魔裁切换角色 [角色名]
    角色名可选：{CHARACTER_NAMES_TEXT}
发送格式如下的消息以生成审判表情包：
【疑问/反驳/伪证/赞同/魔法:[角色名]】这是一个选项文本
    角色名可选：{CHARACTER_NAMES_TEXT}
    可发送多行以添加多个选项
魔裁立绘 [角色名]
    从官方预设开始生成立绘，并通过回复消息精细调整
    发送 魔裁立绘 -h 查看完整帮助
""".strip()

__plugin_meta__ = PluginMetadata(
    name="魔裁 Memes",
    description="生成「魔法少女的魔法审判」的表情包",
    usage=usage,
    type="application",
    homepage="https://github.com/zhaomaoniu/nonebot-plugin-manosaba-memes",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)

CHARACTER_MAP = defaultdict(lambda: get_character("艾玛"))


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
trail_handler = on_regex(
    r"^【(疑问|反驳|伪证|赞同|魔法)(?:[:：]([^】]*))?】(.+)$", flags=re.MULTILINE
)
switch_character_handler = on_alconna(
    Alconna(
        "魔裁切换角色",
        Args["character", str],
        meta=CommandMeta(
            description="切换审判选择中的角色",
            usage=f"魔裁切换角色 [角色名]\n角色名可选：{CHARACTER_NAMES_TEXT}",
            example="魔裁切换角色 希罗",
        ),
    ),
    use_cmd_start=True,
)
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
                "#CFAMVMR9LZ\n"
                "#CFAMVMR9LZ 眼睛"
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
HELP_PATH = Path(__file__).parent / "assets" / "help.jpg"
register_asset_group("魔裁帮助图片", HELP_PATH.parent, ("help.jpg",), lambda path: len(get_b64(path) or ""))


@manohelp_handler.handle()
async def handle_manohelp():
    payload = get_b64(HELP_PATH)
    if payload is None:
        await manohelp_handler.finish("魔裁帮助图片缺失，请联系管理员")
    from nonebot.adapters.onebot.v11 import MessageSegment

    await manohelp_handler.finish(MessageSegment.image(payload))


@anan_says_handler.handle()
async def handle_anan_says(event: Event, result: Arparma):
    user_result = result["text"]
    face = result["face"]
    text = user_result.replace("\\n", "\n")
    try:
        image_bytes = await run_sync(draw_anan, text, face)
    except ValueError as error:
        await anan_says_handler.finish(str(error))
    try:
        async with production_charge(event.get_user_id()):
            await anan_says_handler.send(UniMessage.image(raw=image_bytes, mimetype="image/png"))
    except ChargeRejected as error:
        await anan_says_handler.finish(str(error))
    return


@trail_handler.handle()
async def handle_trail(bot: Bot, event: Event):
    matches = re.findall(
        r"^【(疑问|反驳|伪证|赞同|魔法)(?:[:：]([^】]*))?】(.+)$",
        event.get_message().extract_plain_text(),
        flags=re.MULTILINE,
    )

    options = []
    for statement_type, arg, text in matches:
        try:
            statement_enum = get_statement(statement_type, arg)
        except KeyError:
            if arg:
                await trail_handler.finish(
                    f"角色 {arg} 无效，请从以下选项中选择：{CHARACTER_NAMES_TEXT}"
                )
            else:
                await trail_handler.finish(
                    "魔法类型无效，请输入【魔法:角色】格式。可选的角色有："
                    f"{CHARACTER_NAMES_TEXT}"
                )
        options.append(Option(statement_enum, text))

    try:
        image_bytes = await run_sync(draw_trial, CHARACTER_MAP[event.get_user_id()], options)
    except (OverflowError, ValueError) as error:
        await trail_handler.finish(str(error))
    try:
        async with production_charge(event.get_user_id()):
            await trail_handler.send(await UniMessage.image(raw=image_bytes, mimetype="image/png").export(bot))
    except ChargeRejected as error:
        await trail_handler.finish(str(error))
    return


@switch_character_handler.handle()
async def handle_switch_character(evemt: Event, result: Arparma):
    character_name = result["character"]
    try:
        CHARACTER_MAP[evemt.get_user_id()] = get_character(character_name)
        await switch_character_handler.finish(f"已切换角色为 {character_name}")
    except KeyError:
        await switch_character_handler.finish(
            f"角色名 {character_name} 无效，请选择：{CHARACTER_NAMES_TEXT}"
        )


@sprite_handler.handle()
async def handle_sprite_entry(bot: Bot, event: Event, result: Arparma) -> None:
    await handle_sprite(bot, event, result)


@sprite_followup_handler.handle()
async def handle_sprite_followup_entry(
    bot: Bot, event: Event, message: OriginalUniMsg
) -> None:
    try:
        await handle_sprite_followup(bot, event, message)
    except ChargeRejected as error:
        await sprite_followup_handler.finish(str(error))
