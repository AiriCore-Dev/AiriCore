from nonebot.adapters.onebot.v11 import (
    MessageSegment,
    MessageEvent,
    Bot,
    Message,
    GroupMessageEvent,
)
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from utils.superuser_2fa import SUPERUSER_2FA
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.exception import ActionFailed
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.matcher import Matcher
from nonebot.params import Arg, RegexGroup
from nonebot.log import logger
from nonebot.typing import T_State
from .config import Config
from nonebot import require
from typing import Tuple, Any

try:
    scheduler = require("nonebot_plugin_apscheduler").scheduler
except Exception:
    scheduler = None
    logger.warning("未安装定时插件依赖")
from pathlib import Path
from .check_pass import check_cd, check_max
from . import cache
import os
import re
import nonebot
from httpx import AsyncClient
import random

from utils.onebot_query import bot_name
from utils.copy import COPY
from utils import credit


@nonebot.get_driver().on_shutdown
async def _flush_cache():
    cache.flush()

__plugin_meta__ = PluginMetadata(
    name="今天吃喝什么呢",
    description="随机推荐吃的和喝的",
    config=Config,
    usage="""今天吃什么:随机推荐吃的\n
    今天喝什么:随机推荐喝的\n
    查看菜单:查看所有菜单\n
    查看菜单 菜单名:查看具体菜单\n
    查看饮料:查看所有饮料\n
    查看饮料 饮料名:查看具体饮料\n
    添加菜单 菜名:添加菜单\n
    添加饮料 饮料名:添加饮料\n
    删除菜单 菜名:删除菜单\n
    删除饮料 饮料名:删除饮料""",
    type="application",
    homepage="https://github.com/Cvandia/nonebot-plugin-whateat-pic",
    supported_adapters={"~onebot.v11"},
    extra={
        "unique_name": "nonebot-plugin-whateat-pic",
        "example": """
        今天吃什么\n
        今天喝什么\n
        查看菜单\n
        查看菜单 菜名\n
        查看饮料\n
        查看饮料 饮料名\n
        添加菜单 菜名\n
        添加饮料 饮料名\n
        删除菜单 菜名\n
        删除饮料 饮料名""",
        "author": "divandia <106718176+Cvandia@users.noreply.github.com>",
        "version": "1.1.5",
    },
)

what_eat = on_regex(
    r"^(/)?[今|明|后]?[天|日]?(早|中|晚)?(上|午|餐|饭|夜宵|宵夜)?吃(什么|啥|点啥)$", priority=5
)
what_drink = on_regex(
    r"^(/)?[今|明|后]?[天|日]?(早|中|晚)?(上|午|餐|饭|夜宵|宵夜)?喝(什么|啥|点啥)$", priority=5
)
view_all_dishes = on_regex(r"^(/)?查[看|寻]?全部(菜[单|品]|饮[料|品])$", priority=5)
view_dish = on_regex(r"^(/)?查[看|寻]?(菜[单|品]|饮[料|品])[\s]?(.*)?", priority=5)
add_dish = on_regex(
    r"^(/)?添[加]?(菜[品|单]|饮[品|料])[\s]?(.*)?",
    priority=99,
    permission=SUPERUSER_2FA,
)
del_dish = on_regex(
    r"^(/)?删[除]?(菜[品|单]|饮[品|料])[\s]?(.*)?",
    priority=5,
    permission=SUPERUSER_2FA,
)

img_eat_path = Path(os.path.join(os.path.dirname(__file__), "eat_pic"))

img_drink_path = Path(os.path.join(os.path.dirname(__file__), "drink_pic"))


def _menu_files(path: Path):
    try:
        return os.listdir(str(path))
    except OSError:
        return []

DEFAULT_NICKNAME = Config.parse_obj(nonebot.get_driver().config.dict()).bot_nickname
bot_nicknames = {}


def get_nickname(bot: Bot = None) -> str:
    if bot is None:
        return DEFAULT_NICKNAME
    return bot_nicknames.get(bot.self_id, DEFAULT_NICKNAME)


@nonebot.get_driver().on_bot_connect
async def _load_bot_nickname(bot: Bot):
    try:
        nickname = await bot_name(bot, DEFAULT_NICKNAME)
        if nickname:
            bot_nicknames[bot.self_id] = nickname
    except Exception as e:
        logger.warning(f"获取 Airi 登录昵称失败: {e!r}")


@nonebot.get_driver().on_bot_disconnect
async def _drop_bot_nickname(bot: Bot):
    bot_nicknames.pop(bot.self_id, None)


@del_dish.handle()
async def got_dish_name(state: T_State, matcher: Matcher, args:Tuple[Any,...] = RegexGroup()):
    state["type"] = args[1]
    if args[2]:
        matcher.set_arg("name", args[2])


@del_dish.got("name", prompt="请告诉我你要删除哪个菜品或饮料,发送“取消”可取消操作")
async def del_(state: T_State, name: Message = Arg()):
    if str(name) == "取消":
        await del_dish.finish(COPY["CANCELLED"])
    if state["type"] in ["菜单", "菜品"]:
        img = img_eat_path / (str(name) + ".jpg")
    elif state["type"] in ["饮料", "饮品"]:
        img = img_drink_path / (str(name) + ".jpg")

    try:
        os.remove(img)
    except OSError:
        await del_dish.finish(f"不存在该{state['type']}，请检查下菜单再重试吧")
    cache.invalidate(img)
    await del_dish.send(f"已成功删除{state['type']}:{name}", at_sender=True)


@add_dish.handle()
async def got_dish_name(matcher: Matcher, state: T_State, args:Tuple[Any,...] = RegexGroup()):
    state["type"] = args[1]
    if args[2]:
        matcher.set_arg("dish_name", args[2])


@add_dish.got("dish_name", prompt="⭐请发送名字\n发送“取消”可取消添加")
async def got(state: T_State, dish_name: Message = Arg()):
    state["name"] = str(dish_name)
    if str(dish_name) == "取消":
        await add_dish.finish(COPY["CANCELLED"])


@add_dish.got("img", prompt="⭐图片也发给我吧\n发送“取消”可取消添加")
async def handle(state: T_State, img: Message = Arg()):
    if str(img) == "取消":
        await add_dish.finish(COPY["CANCELLED"])
    img_url = extract_image_urls(img)
    if not img_url:
        await add_dish.finish(f"没有找到图片(╯▔皿▔)╯，{COPY['TRY_LATER']}", at_sender=True)

    if state["type"] in ["菜品", "菜单"]:
        path = img_eat_path
    elif state["type"] in ["饮料", "饮品"]:
        path = img_drink_path
    try:
        async with AsyncClient() as client:
            dish_img = await client.get(url=img_url[0])
            with open(path / str(state["name"] + ".jpg"), "wb") as f:
                f.write(dish_img.content)
        await add_dish.finish(
            f"成功添加{state['type']}:{state['name']}\n" + MessageSegment.image(img_url)
        )
    except Exception:
        await add_dish.finish(f"添加失败，{COPY['TRY_LATER']}", at_sender=True)


@view_dish.handle()
async def got_name(bot: Bot, matcher: Matcher, state: T_State, args:Tuple[Any,...] = RegexGroup()):
    if args[1] in ["菜单", "菜品"]:
        state["type"] = "吃的"
    elif args[1] in ["饮料", "饮品"]:
        state["type"] = "喝的"

    if args[2]:
        matcher.set_arg("name", args[2])
    else:
        await view_dish.send(f"请告诉{get_nickname(bot)}具体菜名或者饮品名吧")


@view_dish.got("name")
async def handle(state: T_State, name: Message = Arg()):
    if state["type"] == "吃的":
        img = img_eat_path / (str(name) + ".jpg")
    elif state["type"] == "喝的":
        img = img_drink_path / (str(name) + ".jpg")

    base64_str = cache.get_b64(img)
    if base64_str is None:
        await view_dish.finish("没有找到你所说的，请检查一下菜单吧", at_sender=True)
    try:
        await view_dish.send(MessageSegment.image(base64_str))
    except ActionFailed:
        await view_dish.finish("没有找到你所说的，请检查一下菜单吧", at_sender=True)


@view_all_dishes.handle()
async def handle(bot: Bot, event: MessageEvent, args:Tuple[Any,...] = RegexGroup()):
    if args[1] in ["菜单", "菜品"]:
        path = img_eat_path
    elif args[1] in ["饮料", "饮品"]:
        path = img_drink_path
    all_name = _menu_files(path)

    msg_list = [f"{get_nickname(bot)}查询到的{args[1]}如下"]
    N = 0
    for name in all_name:
        img = path / name
        base64_str = cache.get_b64(img)
        if base64_str is None:
            continue
        N += 1
        name = re.sub(".jpg", "", name)
        msg_list.append(f"{N}.{name}\n{MessageSegment.image(base64_str)}")
    await send_forward_msg(bot, event, get_nickname(bot), bot.self_id, msg_list)


time = 0
user_count = {}


@what_drink.handle()
async def wtd(bot: Bot, msg: MessageEvent):
    global time, user_count
    user_id = msg.get_user_id()
    check_result, remain_time, new_last_time = check_cd(time)
    if not check_result:
        time = new_last_time
        await what_drink.finish(f"cd冷却中,还有{remain_time}秒", at_sender=True)
    else:
        is_max, user_count = check_max(msg, user_count)
        if is_max:
            await what_drink.finish(random.choice(get_max_msg(get_nickname(bot))), at_sender=True)
        time = new_last_time
        files = _menu_files(img_drink_path)
        if not files:
            await what_drink.finish("出错啦！没有找到好喝的~")
        img_name = random.choice(files)
        img = img_drink_path / img_name
        base64_str = cache.get_b64(img)
        if base64_str is None:
            await what_drink.finish("出错啦！没有找到好喝的~")
        msg = f"\n{get_nickname(bot)}建议你喝: \n⭐{img.stem}⭐\n" + MessageSegment.image(base64_str)
        try:
            receipt = await credit.charge(user_id, credit.WHATEAT_PIC_COST)
        except credit.ChargeRejected as error:
            await what_drink.finish(str(error))
        try:
            await what_drink.send(msg, at_sender=True)
        except Exception:
            await credit.refund(receipt)
            await what_drink.finish("出错啦！没有找到好喝的~")


@what_eat.handle()
async def wte(bot: Bot, msg: MessageEvent):
    global time, user_count
    user_id = msg.get_user_id()
    check_result, remain_time, new_last_time = check_cd(time)
    if not check_result:
        time = new_last_time
        await what_eat.finish(f"cd冷却中,还有{remain_time}秒", at_sender=True)
    else:
        is_max, user_count = check_max(msg, user_count)
        if is_max:
            await what_eat.finish(random.choice(get_max_msg(get_nickname(bot))), at_sender=True)
        time = new_last_time
        files = _menu_files(img_eat_path)
        if not files:
            await what_eat.finish("出错啦！没有找到好吃的~")
        img_name = random.choice(files)
        img = img_eat_path / img_name
        base64_str = cache.get_b64(img)
        if base64_str is None:
            await what_eat.finish("出错啦！没有找到好吃的~")
        msg = f"\n{get_nickname(bot)}建议你吃: \n⭐{img.stem}⭐\n" + MessageSegment.image(base64_str)
        try:
            receipt = await credit.charge(user_id, credit.WHATEAT_PIC_COST)
        except credit.ChargeRejected as error:
            await what_eat.finish(str(error))
        try:
            await what_eat.send(msg, at_sender=True)
        except Exception:
            await credit.refund(receipt)
            await what_eat.finish("出错啦！没有找到好吃的~")






def reset_user_count():
    global user_count
    user_count = {}


try:
    scheduler.add_job(reset_user_count, "cron", hour="0", id="delete_date")
except ActionFailed as e:
    logger.warning(f"定时任务添加失败，{repr(e)}")


def get_max_msg(nickname):
    return (
        "你今天吃的够多了！不许再吃了(´-ωก`)",
        "吃吃吃，就知道吃，你都吃饱了！明天再来(▼皿▼#)",
        "(*｀へ´*)你猜我会不会再给你发好吃的图片",
        f"没得吃的了，{nickname}的食物都被你这坏蛋吃光了！",
        "你在等我给你发好吃的？做梦哦！你都吃那么多了，不许再吃了！ヽ(≧Д≦)ノ",
    )


async def send_forward_msg(
    bot: Bot,
    event: MessageEvent,
    name: str,
    uin: str,
    msgs: list,
) -> dict:
    def to_json(msg: Message):
        return {"type": "node", "data": {"name": name, "uin": uin, "content": msg}}

    messages = [to_json(msg) for msg in msgs]
    if isinstance(event, GroupMessageEvent):
        return await bot.call_api(
            "send_group_forward_msg", group_id=event.group_id, messages=messages
        )
    else:
        return await bot.call_api(
            "send_private_forward_msg", user_id=event.user_id, messages=messages
        )
