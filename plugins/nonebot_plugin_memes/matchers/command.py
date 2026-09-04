import random
import re
import traceback
from itertools import chain
from typing import Any, Optional, Union

from arclet.alconna import Arparma, command_manager, output_manager
from arclet.alconna import config as alc_config
from meme_generator import (
    BooleanOption,
    DeserializeError,
    FloatOption,
    ImageAssetMissing,
    ImageDecodeError,
    ImageEncodeError,
    ImageNumberMismatch,
    IntegerOption,
    Meme,
    MemeFeedback,
    MemeShortcut,
    StringOption,
    TextNumberMismatch,
    TextOverLength,
)
from meme_generator import Image as MemeImage
from nonebot import get_driver, on_message
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.exception import AdapterException
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.typing import T_Handler, T_State
from nonebot.utils import run_sync
from utils.copy import COPY
from utils import credit
from nonebot_plugin_alconna import (
    AlcMatches,
    Alconna,
    Args,
    At,
    Image,
    MultiVar,
    Option,
    Text,
    UniMessage,
    UniMsg,
    on_alconna,
    store_false,
    store_true,
)
from nonebot_plugin_alconna.builtins.extensions.reply import ReplyMergeExtension
from nonebot_plugin_alconna.uniseg.constraint import UNISEG_MESSAGE
from nonebot_plugin_alconna.uniseg.tools import image_fetch
from nonebot_plugin_uninfo.model import Session
from nonebot_plugin_waiter import waiter

from utils.onebot_query import (
    avatar_url,
    event_nickname,
    event_session,
    member_name,
    session_key,
)

from ..config import memes_config
from ..manager import meme_manager
from ..recorder import record_meme_generation

alc_config.command_max_count += 1000


async def process(
    bot: Bot,
    event: Event,
    state: T_State,
    matcher: Matcher,
    session: Session,
    meme: Meme,
    images: list[Image],
    texts: list[str],
    options: dict[str, Any] = {},
    show_info: bool = False,
):
    meme_images: list[MemeImage] = []

    try:
        for image in images:
            result = await image_fetch(event, bot, state, image)
            if not isinstance(result, bytes):
                raise NotImplementedError
            meme_images.append(MemeImage(image.name, result))
    except NotImplementedError:
        await matcher.finish("当前平台可能不支持下载图片")
    except AdapterException:
        logger.warning(traceback.format_exc())
        await matcher.finish(COPY["IMAGE_DOWNLOAD_FAILED"])

    result = await run_sync(meme.generate)(meme_images, texts, options)

    if isinstance(result, ImageDecodeError):
        await matcher.finish(f"图片解码出错：{result.error}")
    elif isinstance(result, ImageEncodeError):
        await matcher.finish(f"图片编码出错：{result.error}")
    elif isinstance(result, ImageAssetMissing):
        await matcher.finish(f"缺少图片资源：{result.path}")
    elif isinstance(result, DeserializeError):
        await matcher.finish(f"表情选项解析出错：{result.error}")
    elif isinstance(result, ImageNumberMismatch):
        num = (
            f"{result.min} ~ {result.max}"
            if result.min != result.max
            else str(result.min)
        )
        await matcher.finish(f"图片数量不符，应为 {num}，实际传入 {result.actual}")
    elif isinstance(result, TextNumberMismatch):
        num = (
            f"{result.min} ~ {result.max}"
            if result.min != result.max
            else str(result.min)
        )
        await matcher.finish(f"文字数量不符，应为 {num}，实际传入 {result.actual}")
    elif isinstance(result, TextOverLength):
        text = result.text
        repr = text if len(text) <= 10 else (text[:10] + "...")
        await matcher.finish(f"文字过长：{repr}")
    elif isinstance(result, MemeFeedback):
        await matcher.finish(result.feedback)

    try:
        receipt = await credit.charge(event.get_user_id(), credit.MEMES_COST)
    except credit.ChargeRejected as error:
        await matcher.finish(str(error))

    try:
        await record_meme_generation(session, meme.key)
        msg = UniMessage()
        if show_info:
            keywords = "、".join([f'"{keyword}"' for keyword in meme.info.keywords])
            msg += f"关键词：{keywords}"
        msg += UniMessage.image(raw=result)
        await msg.send()
    except Exception:
        await credit.refund(receipt)
        raise


T_MemeParams = Union[Text, Image, At]
meme_params_key = "meme_params"
arg_meme_params = Args[meme_params_key, MultiVar(T_MemeParams, "*")]


async def handle_params(
    bot: Bot,
    event: MessageEvent,
    meme_params: list[T_MemeParams],
):
    texts: list[str] = []
    images: list[Image] = []
    names: list[str] = []

    for msg_seg in meme_params:
        if isinstance(msg_seg, At):
            target = str(msg_seg.target)
            name = (
                await member_name(bot, event.group_id, target)
                if isinstance(event, GroupMessageEvent)
                else target
            )
            images.append(Image(name=name, url=avatar_url(target)))

        elif isinstance(msg_seg, Image):
            images.append(msg_seg)

        elif isinstance(msg_seg, Text):
            text = msg_seg.text
            if text.startswith("@") and (target := text[1:]):
                name = (
                    await member_name(bot, event.group_id, target)
                    if isinstance(event, GroupMessageEvent)
                    else target
                )
                images.append(Image(name=name, url=avatar_url(target)))

            elif text == "自己":
                images.append(
                    Image(
                        name=event_nickname(event),
                        url=avatar_url(event.get_user_id()),
                    )
                )

            elif text.startswith("#"):
                names.append(text[1:])

            elif text:
                texts.append(text)

    return texts, images, names


def build_option(
    option: Union[BooleanOption, IntegerOption, StringOption, FloatOption],
) -> Option:
    names: list[str] = []
    parser_flags = option.parser_flags
    short_aliases = parser_flags.short_aliases
    if parser_flags.short:
        short_aliases.insert(0, option.name[0])
    long_aliases = parser_flags.long_aliases
    if parser_flags.long:
        long_aliases.insert(0, option.name)
    names.extend([f"-{flag}" for flag in short_aliases])
    names.extend([f"--{flag}" for flag in long_aliases])

    if isinstance(option, BooleanOption):
        action = None
        if option.default is not None:
            action = store_false if option.default else store_true
        return Option(
            name="|".join(names),
            dest=option.name,
            default=option.default,
            action=action,
            help_text=option.description,
        )

    else:
        args = Args()
        if isinstance(option, IntegerOption):
            arg_type = int
        elif isinstance(option, FloatOption):
            arg_type = float
        else:
            arg_type = str
        args.add(name=option.name, value=arg_type)
        return Option(
            name="|".join(names),
            args=args,
            dest=option.name,
            help_text=option.description,
        )


prefixes = list(get_driver().config.command_start)
if (meme_prefixes := memes_config.memes_command_prefixes) is not None:
    prefixes = meme_prefixes


_reply_ext = ReplyMergeExtension()
_keyword_entries: list[tuple[str, Alconna, T_Handler]] = []
_shortcut_entries: list[tuple[Optional[re.Pattern], Alconna, T_Handler]] = []


def _gate_pattern(pattern: str) -> Optional[re.Pattern]:
    probe = pattern
    while probe.startswith("^"):
        probe = probe[1:]
    if "\\A" in probe:
        return None
    try:
        return re.compile(probe, re.IGNORECASE)
    except re.error:
        return None


def create_matcher(meme: Meme):
    info = meme.info
    params = info.params
    options = [build_option(opt) for opt in (params.options)]

    keyword_handler = create_handler(meme)
    for keyword in info.keywords:
        command = Alconna(prefixes, keyword, *options, arg_meme_params)
        _keyword_entries.append((keyword.lower(), command, keyword_handler))

    for shortcut in info.shortcuts:
        command = Alconna(prefixes, f"re:{shortcut.pattern}", *options, arg_meme_params)
        _shortcut_entries.append(
            (_gate_pattern(shortcut.pattern), command, create_handler(meme, shortcut))
        )


def create_handler(meme: Meme, shortcut: Optional[MemeShortcut] = None) -> T_Handler:
    async def handler(
        bot: Bot,
        event: MessageEvent,
        state: T_State,
        matcher: Matcher,
        user_id: str,
        session: Session,
        alc_matches: AlcMatches,
    ):
        if not meme_manager.check(user_id, meme.key):
            logger.info(f"用户 {user_id} 表情 {meme.key} 被禁用")
            return

        texts: list[str] = []
        images: list[Image] = []
        names: list[str] = []
        options: dict[str, Any] = {}

        if shortcut:
            args = alc_matches.header
            names = [name.format(**args) for name in shortcut.names]
            texts = [text.format(**args) for text in shortcut.texts]
            options = {
                name: value.format(**args) if isinstance(value, str) else value
                for name, value in shortcut.options.items()
            }

        alc_options = alc_matches.options
        for option, option_result in alc_options.items():
            if option_result.value is None:
                options.update(option_result.args)
            else:
                options[option] = option_result.value

        meme_params: list[T_MemeParams] = list(alc_matches.query(meme_params_key, ()))
        alc_texts, images, alc_names = await handle_params(bot, event, meme_params)
        texts.extend(alc_texts)
        names.extend(alc_names)
        for i in range(len(names)):
            if i < len(images):
                images[i].name = names[i]

        info = meme.info
        params = info.params

        if params.min_images == 2 and len(images) == 1:
            images.insert(
                0,
                Image(
                    name=event_nickname(event),
                    url=avatar_url(event.get_user_id()),
                ),
            )

        if memes_config.memes_use_sender_when_no_image and (
            params.min_images == 1 and len(images) == 0
        ):
            images.append(
                Image(
                    name=event_nickname(event),
                    url=avatar_url(event.get_user_id()),
                )
            )

        if memes_config.memes_use_default_when_no_text and (
            params.min_texts > 0 and len(texts) == 0
        ):
            texts = params.default_texts

        @waiter(waits=["message"], keep_session=True)
        async def get_texts(uni_msg: UniMsg):
            uni_texts = [seg for seg in uni_msg if isinstance(seg, Text)]
            uni_texts = chain.from_iterable(
                [seg.split() for seg in uni_texts if seg.text]
            )
            return [seg.text for seg in uni_texts if seg.text]

        @waiter(waits=["message"], keep_session=True)
        async def get_images(uni_msg: UniMsg):
            uni_segs = chain.from_iterable(
                list(msg) for msg in uni_msg.include(Image, At, Text).split()
            )
            params: list[T_MemeParams] = list(uni_segs)
            _, new_images, new_names = await handle_params(bot, event, params)
            for i in range(len(new_names)):
                if i < len(new_images):
                    new_images[i].name = new_names[i]
            return new_images

        policy = memes_config.memes_params_mismatch_policy

        text_range = (
            f"{params.min_texts} ~ {params.max_texts}"
            if params.min_texts != params.max_texts
            else str(params.min_texts)
        )
        image_range = (
            f"{params.min_images} ~ {params.max_images}"
            if params.min_images != params.max_images
            else str(params.min_images)
        )

        if len(texts) < params.min_texts:
            msg = f"文字数量不符，应为 {text_range}，实际传入 {len(texts)}"
            if policy.too_few_text == "ignore":
                logger.info(msg)
                await matcher.finish()

            if policy.too_few_text == "prompt":
                matcher.stop_propagation()
                await matcher.finish(msg)

            elif policy.too_few_text == "get":
                while len(texts) < params.min_texts:
                    min = params.min_texts - len(texts)
                    max = params.max_texts - len(texts)
                    num = f"{min} ~ {max}" if min != max else str(min)
                    await matcher.send(f"请继续发送 {num} 段文字")
                    resp = await get_texts.wait(timeout=30)
                    if resp is None:
                        await matcher.finish()
                    texts.extend(resp)
                    texts = texts[: params.max_texts]

        if len(texts) > params.max_texts:
            msg = f"文字数量不符，应为 {text_range}，实际传入 {len(texts)}"
            if policy.too_much_text == "ignore":
                logger.info(msg)
                await matcher.finish()

            if policy.too_much_text == "prompt":
                matcher.stop_propagation()
                await matcher.finish(msg)

            elif policy.too_much_text == "drop":
                texts = texts[: params.max_texts]

        if len(images) < params.min_images:
            msg = f"图片数量不符，应为 {image_range}，实际传入 {len(images)}"
            if policy.too_few_image == "ignore":
                logger.info(msg)
                await matcher.finish()

            if policy.too_few_image == "prompt":
                matcher.stop_propagation()
                await matcher.finish(msg)

            elif policy.too_few_image == "get":
                while len(images) < params.min_images:
                    min = params.min_images - len(images)
                    max = params.max_images - len(images)
                    num = f"{min} ~ {max}" if min != max else str(min)
                    await matcher.send(f"请继续发送 {num} 张图片")
                    resp = await get_images.wait(timeout=30)
                    if resp is None:
                        await matcher.finish()
                    images.extend(resp)
                    images = images[: params.max_images]

        if len(images) > params.max_images:
            msg = f"图片数量不符，应为 {image_range}，实际传入 {len(images)}"
            if policy.too_much_image == "ignore":
                logger.info(msg)
                await matcher.finish()

            if policy.too_much_image == "prompt":
                matcher.stop_propagation()
                await matcher.finish(msg)

            elif policy.too_much_image == "drop":
                images = images[: params.max_images]

        matcher.stop_propagation()
        await process(bot, event, state, matcher, session, meme, images, texts, options)

    return handler


def create_matchers():
    for meme in meme_manager.get_memes():
        create_matcher(meme)


create_matchers()


_auto_send_output = getattr(get_driver().config, "alconna_auto_send_output", None)
_auto_send_output = True if _auto_send_output is None else bool(_auto_send_output)

memes_matcher = on_message(priority=12, block=False)


async def _uni_message(bot: Bot, event: Event, state: T_State) -> Optional[UniMessage]:
    try:
        msg = await _reply_ext.message_provider(event, state, bot)
    except Exception:
        msg = None
    if msg is not None:
        return msg
    try:
        return UniMessage.of(event.get_message(), bot=bot)
    except (NotImplementedError, ValueError):
        return None


def _candidates(text: str) -> list[tuple[Alconna, T_Handler]]:
    lowered = text.lower()
    picked: list[tuple[int, Alconna, T_Handler]] = []
    for keyword, command, handler in _keyword_entries:
        if keyword in lowered:
            picked.append((len(keyword), command, handler))
    for regex, command, handler in _shortcut_entries:
        if regex is None or regex.search(text):
            picked.append((0, command, handler))
    picked.sort(key=lambda item: item[0], reverse=True)
    return [(command, handler) for _, command, handler in picked]


@memes_matcher.handle()
async def _(
    bot: Bot,
    event: MessageEvent,
    state: T_State,
    matcher: Matcher,
):
    try:
        if event.get_user_id() == bot.self_id:
            return
        text = event.get_plaintext()
    except (NotImplementedError, ValueError):
        return

    candidates = _candidates(text)
    if not candidates:
        return

    user_id = session_key(event)
    session = event_session(bot, event)

    msg = await _uni_message(bot, event, state)
    if msg is None:
        return

    Arparma._additional.update(bot=lambda: bot, event=lambda: event, state=lambda: state)
    state[UNISEG_MESSAGE] = msg

    for command, handler in candidates:
        if command_manager.is_disable(command):
            continue
        with output_manager.capture(command.name) as cap:
            output_manager.set_action(lambda x: x, command.name)
            try:
                arp = command.parse(msg)
            except Exception as e:
                logger.warning(f"表情命令解析出错 {command.path}: {e}")
                continue
            output = cap.get("output", None)
        if not arp.head_matched:
            continue
        if output:
            if _auto_send_output:
                await matcher.send(output)
            return
        if not arp.matched:
            return
        await handler(
            bot=bot,
            event=event,
            state=state,
            matcher=matcher,
            user_id=user_id,
            session=session,
            alc_matches=arp,
        )
        return


random_matcher = on_alconna(
    Alconna("随机表情", arg_meme_params),
    block=False,
    priority=12,
    use_cmd_start=True,
    extensions=[ReplyMergeExtension()],
)


@random_matcher.handle()
async def _(
    bot: Bot,
    event: MessageEvent,
    state: T_State,
    matcher: Matcher,
    alc_matches: AlcMatches,
):
    user_id = session_key(event)
    session = event_session(bot, event)
    meme_params: list[T_MemeParams] = list(alc_matches.query(meme_params_key, ()))
    texts, images, names = await handle_params(bot, event, meme_params)
    for i in range(len(names)):
        if i < len(images):
            images[i].name = names[i]

    available_memes = [
        meme
        for meme in meme_manager.get_memes()
        if meme_manager.check(user_id, meme.key)
        and (
            (meme.info.params.min_images <= len(images) <= meme.info.params.max_images)
            and (meme.info.params.min_texts <= len(texts) <= meme.info.params.max_texts)
        )
    ]
    if not available_memes:
        await matcher.finish("找不到符合参数数量的表情")

    random_meme = random.choice(available_memes)
    await process(
        bot,
        event,
        state,
        matcher,
        session,
        random_meme,
        images,
        texts,
        show_info=memes_config.memes_random_meme_show_info,
    )
