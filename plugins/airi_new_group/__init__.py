import os
import asyncio
import base64
import re
import nonebot
from utils.cache import get_b64
from utils.network import download_public_bytes
from utils.totp_2fa import totp_verify
from nonebot import on_notice, on_command, get_driver, logger
from nonebot.permission import SUPERUSER
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import GroupIncreaseNoticeEvent, Message
from nonebot.adapters.onebot.v11.bot import Bot, MessageSegment

driver = get_driver()
_2fa_key = str(getattr(driver.config, "_2fa_key", "") or "").strip()
BROADCAST_INTERVAL = 2
BROADCAST_MAX_GROUPS = 2000
BROADCAST_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_DATA_IMAGE_RE = re.compile(r"^data:image/[^;]+;base64,(.+)$", re.I | re.S)
_IMAGE_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
)


def localpath_to_base64(pth):
    data = get_b64(pth)
    if data is None:
        logger.warning(f"airi_new_group 素材缺失: {pth}")
    return data

intro = """Lovely！Fairy！Momoi Airi！
本Bot是一款基于 AiriCore 的高性能QQ群Bot，功能请发送 help 查看。
Bot一群：1030569383
Bot二群：808085026
AiriCore 分布式群：1084667424
Bot官网：www.airi.asia
本Bot是完全公益的，不接受任何形式的收费和赞助。如果你遇到收费拉群、索要赞助等情况，请联系bot主举报！
bot主联系邮箱：saki@saki.ln.cn
"""

img = localpath_to_base64(os.path.join(os.path.dirname(__file__), 'airi.jpg'))
duang = localpath_to_base64(os.path.join(os.path.dirname(__file__), 'duang.wav'))
msg = MessageSegment.text(intro) + MessageSegment.image(img) if img else MessageSegment.text(intro)

_raw_full_group_whitelist = getattr(driver.config, "airifullgroup_bot_whitelist", None)
if _raw_full_group_whitelist is None:
    airifullgroup_bot_whitelist = []
elif isinstance(_raw_full_group_whitelist, str):
    airifullgroup_bot_whitelist = [
        b.strip() for b in _raw_full_group_whitelist.split(",") if b.strip()
    ]
else:
    airifullgroup_bot_whitelist = [
        str(b).strip() for b in _raw_full_group_whitelist if str(b).strip()
    ]

group_increase = on_notice(priority=5, block=False)

@group_increase.handle()
async def handle_group_increase(bot: Bot, event: GroupIncreaseNoticeEvent):
    try:
        bot_id = str(bot.self_id)
        user_id = str(event.user_id)

        if user_id == bot_id:
            group_id = event.group_id
            bot_list = list(nonebot.get_bots().values())
            bot_list = [str(x.self_id) for x in bot_list]
            group_member_list = await bot.get_group_member_list(group_id=group_id)
            group_member_list = [str(x['user_id']) for x in group_member_list]

            target_bots = []
            for botq in bot_list:
                if botq in group_member_list and botq != bot_id:
                    target_bots.append(botq)

            if not len(target_bots):
                if duang:
                    await bot.send_group_msg(group_id=group_id, message=MessageSegment.record(duang))
                await bot.send_group_msg(group_id=group_id, message=msg)
            else:
                logger.opt(colors=True).info(
                    f"<y>群{group_id} 已有同项目 Bot（{', '.join(target_bots)}），静默入群</y>"
                )

    except Exception as e:
        logger.warning(f"处理入群事件时发生错误：{e}")


airi_full_group = on_command('airifullgroup', priority=5, block=True, permission=SUPERUSER)


def _is_image_data(data: bytes) -> bool:
    return (
        any(data.startswith(signature) for signature in _IMAGE_SIGNATURES)
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )


def _as_base64_image(data: bytes) -> str | None:
    if not data or len(data) > BROADCAST_MAX_IMAGE_BYTES or not _is_image_data(data):
        return None
    return "base64://" + base64.b64encode(data).decode("ascii")


def _embedded_image(source: str) -> str | None:
    value = str(source or "").strip()
    encoded = value[9:] if value.startswith("base64://") else ""
    if not encoded:
        match = _DATA_IMAGE_RE.match(value)
        if not match:
            return None
        encoded = match.group(1)
    try:
        return _as_base64_image(base64.b64decode(encoded, validate=True))
    except Exception:
        return None


def _local_image(source: str) -> str | None:
    try:
        with open(source, "rb") as file:
            return _as_base64_image(file.read(BROADCAST_MAX_IMAGE_BYTES + 1))
    except OSError:
        return None


async def _image_as_base64(data: dict, bot: Bot) -> str | None:
    sources = []
    for key in ("url", "file"):
        source = data.get(key)
        if source and source not in sources:
            sources.append(str(source))
    for source in sources:
        embedded = _embedded_image(source)
        if embedded:
            return embedded
        if source.startswith(("http://", "https://")):
            try:
                image = _as_base64_image(await download_public_bytes(
                    source, BROADCAST_MAX_IMAGE_BYTES
                ))
            except Exception as error:
                logger.warning(f"全群广播图片下载失败: {type(error).__name__}: {error}")
                continue
            if image:
                return image
    image_id = data.get("file")
    if not image_id:
        return None
    try:
        info = await bot.get_image(file=image_id)
    except Exception as error:
        logger.warning(f"全群广播无法获取图片: {type(error).__name__}: {error}")
        return None
    if not isinstance(info, dict):
        return None
    for key in ("url", "file"):
        source = info.get(key)
        if not source:
            continue
        source = str(source)
        embedded = _embedded_image(source)
        if embedded:
            return embedded
        if source.startswith(("http://", "https://")):
            try:
                image = _as_base64_image(await download_public_bytes(
                    source, BROADCAST_MAX_IMAGE_BYTES
                ))
            except Exception as error:
                logger.warning(f"全群广播图片下载失败: {type(error).__name__}: {error}")
                continue
            if image:
                return image
        else:
            image = _local_image(source)
            if image:
                return image
    return None


async def _parse_broadcast_argument(arg: Message, bot: Bot) -> tuple[str | None, list]:
    digit = None
    content = []
    for segment in arg:
        if segment.type == "text":
            value = str(segment.data.get("text", ""))
            if digit is None:
                match = re.match(r"\s*(\S+)", value)
                if not match:
                    continue
                digit = match.group(1)
                value = value[match.end():].lstrip()
            if value:
                content.append(MessageSegment.text(value))
        elif digit is not None and segment.type == "image":
            image = await _image_as_base64(dict(segment.data), bot)
            if image is None:
                return digit, []
            content.append(MessageSegment.image(image))
    return digit, content


@airi_full_group.handle()
async def _(bot: Bot, arg: Message = CommandArg()):
    if not _2fa_key:
        await airi_full_group.finish("未配置 _2fa_key，全群广播已禁用。")

    digit, content = await _parse_broadcast_argument(arg, bot)
    if not digit:
        await airi_full_group.finish("用法：airifullgroup <2FA验证码> [广播内容]")

    if not totp_verify(_2fa_key, digit):
        await airi_full_group.finish("2fa verification failed")

    if any(segment.type == "image" for segment in arg) and not content:
        await airi_full_group.finish("图片解析失败，广播未开始。")

    target_content = content or list(msg)

    targets = []
    for bot_instance in nonebot.get_bots().values():
        if str(bot_instance.self_id) not in airifullgroup_bot_whitelist:
            continue
        try:
            gr_list = await bot_instance.get_group_list()
        except Exception as e:
            logger.warning(f"获取群列表失败（{bot_instance.self_id}）：{e}")
            continue
        for gr in gr_list:
            targets.append((bot_instance, gr["group_id"]))

    if not targets:
        await airi_full_group.finish("没有可广播的群，请检查 airifullgroup_bot_whitelist 配置。")

    truncated = len(targets) > BROADCAST_MAX_GROUPS
    targets = targets[:BROADCAST_MAX_GROUPS]
    est = len(targets) * BROADCAST_INTERVAL
    await airi_full_group.send(
        f"开始向 {len(targets)} 个群广播，预计耗时约 {est // 60} 分 {est % 60} 秒。"
        + ("（已截断至上限）" if truncated else "")
    )

    ok = 0
    failed = 0
    target_message = Message(target_content)
    for bot_instance, gid in targets:
        try:
            await bot_instance.send_group_msg(group_id=gid, message=target_message)
            ok += 1
        except Exception as e:
            failed += 1
            logger.warning(f"发送群消息失败（群{gid}）：{e}")
        await asyncio.sleep(BROADCAST_INTERVAL)

    await airi_full_group.finish(f"广播完成：成功 {ok} 个群，失败 {failed} 个群。")
