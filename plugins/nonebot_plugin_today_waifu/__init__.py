import re
import random
import datetime
import asyncio
import weakref
from typing import Set, Dict, Any, Union, List

import nonebot
from nonebot import on_regex
from nonebot.params import RegexDict
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import GROUP, GroupMessageEvent, Message
from nonebot.adapters.onebot.v11.permission import GROUP_OWNER, GROUP_ADMIN
from utils.superuser_2fa import SUPERUSER_2FA

from .config import Config
from .record import get_group_record, save_group_record, construct_waifu_msg, clear_group_record, \
    construct_change_waifu_msg, construct_force_waifu_msg, construct_force_waifu_taken_msg

__plugin_name__ = '今日老婆'
__plugin_version__ = '0.1.5'
__plugin_meta__ = PluginMetadata(
    __plugin_name__,
    "随机抽取群友作为老婆吧！",
    (
        "指令表：\n"
        "▶ 今日老婆\n"
        "  ▷ 范围：群聊\n"
        "  ▷ 介绍：随机抽取群友作为老婆，返回头像和昵称。当天已经抽取过回复相同老婆\n"
        "▶ 换老婆\n"
        "  ▷ 范围：群聊\n"
        "  ▷ 介绍：重新抽取老婆\n"
        "▶ (刷新/重置)今日老婆 | (刷新/重置)自定义别名\n"
        "  ▷ 权限：主人\n"
        "  ▷ 范围：群聊\n"
        "  ▷ 介绍：清空今日本群老婆数据\n"
        "▶ (开启/关闭)换老婆\n"
        "  ▷ 权限：主人/群主/管理员\n"
        "  ▷ 范围：群聊\n"
        "  ▷ 介绍：开启/关闭本群换老婆功能\n"
        "▶ 设置换老婆次数 <N>\n"
        "  ▷ 权限：主人/群主/管理员\n"
        "  ▷ 范围：群聊\n"
        "  ▷ 介绍：设置本群换老婆最大次数\n"
        "  ▷ 参数：\n"
        "    ▷ N：指定整数次数\n"
        "▶ 强娶 @某人\n"
        "  ▷ 范围：群聊\n"
        "  ▷ 介绍：强制指定某人为今日老婆，若对方已被娶走则提示；成功后今日换老婆次数清零"
    ),
    Config,
    {
        "License": "MIT",
        "Author": "glamorgan9826",
        "version": __plugin_version__,
    },
)

global_config = nonebot.get_driver().config
waifu_config: Config = Config.parse_obj(global_config.dict())

plugin_aliases: List[str] = waifu_config.today_waifu_aliases
ban_id: Set[int] = waifu_config.today_waifu_ban_id_list
default_allow_change_waifu: bool = waifu_config.today_waifu_default_change_waifu
default_limit_times: int = waifu_config.today_waifu_default_limit_times
today_waifu_superuser_opt: bool = waifu_config.today_waifu_superuser_opt
if today_waifu_superuser_opt:
    permission_opt = SUPERUSER_2FA
else:
    permission_opt = SUPERUSER_2FA | GROUP_OWNER | GROUP_ADMIN

_group_locks = weakref.WeakValueDictionary()


def _member_map(members):
    return {
        int(member["user_id"]): member
        for member in members
        if member.get("user_id") is not None
    }


def _group_lock(gid: str) -> asyncio.Lock:
    lock = _group_locks.get(gid)
    if lock is None:
        lock = asyncio.Lock()
        _group_locks[gid] = lock
    return lock

PatternStr = '|'.join([__plugin_name__, ] + plugin_aliases)

today_waifu = on_regex(
    pattern=rf'^\s*({PatternStr})\s*$',
    flags=re.S,
    permission=GROUP | SUPERUSER_2FA,
    priority=7,
    block=True,
)

today_waifu_refresh = on_regex(
    rf"^\s*(刷新|重置)(?P<name>{PatternStr})\s*$",
    permission=SUPERUSER_2FA,
    priority=7,
    block=True
)

today_waifu_change = on_regex(
    pattern=r'^\s*(换老婆|hlp)\s*$',
    flags=re.S,
    permission=GROUP | SUPERUSER_2FA,
    priority=7,
    block=True,
)

today_waifu_set_limit_times = on_regex(
    pattern=rf"^\s*设置换老婆次数\s*(?P<times>\d+)\s*$",
    permission=permission_opt,
    priority=7,
    block=True
)

today_waifu_set_allow_change = on_regex(
    pattern=rf"^\s*(?P<val>开启换老婆|关闭换老婆)\s*$",
    permission=permission_opt,
    priority=7,
    block=True
)

today_waifu_force = on_regex(
    pattern=r'^\s*强娶',
    flags=re.S,
    permission=GROUP | SUPERUSER_2FA,
    priority=7,
    block=True,
)


async def _handle_set_allow_change(event: GroupMessageEvent, val: Dict[str, Any]):
    gid = str(event.group_id)
    group_record: Dict[str, Union[bool, Dict[str, Dict[str, int]]]] = get_group_record(gid)
    val: str = val.get('val', '').strip()
    if val == '开启换老婆':
        group_record['allow_change_waifu'] = True
    elif val == '关闭换老婆':
        group_record['allow_change_waifu'] = False
    else:
        await today_waifu_set_allow_change.finish()
    save_group_record(gid, group_record)
    await today_waifu_set_allow_change.finish(f'本群设置为{val}')


@today_waifu_set_allow_change.handle()
async def _(event: GroupMessageEvent, val: Dict[str, Any] = RegexDict()):
    async with _group_lock(str(event.group_id)):
        await _handle_set_allow_change(event, val)


async def _handle_set_limit_times(event: GroupMessageEvent, times: Dict[str, Any]):
    limit_times: str = times.get('times', str(default_limit_times)).strip()
    try:
        limit_times_num = int(limit_times)
    except ValueError:
        await today_waifu_set_limit_times.finish('换老婆次数应为整数')
        return
    gid = str(event.group_id)
    group_record: Dict[str, Union[int, Dict[str, Dict[str, int]]]] = get_group_record(gid)
    group_record['limit_times'] = limit_times_num
    save_group_record(gid, group_record)
    await today_waifu_set_limit_times.finish(f'已将本群换老婆次数设置为{limit_times_num}次')


@today_waifu_set_limit_times.handle()
async def _(event: GroupMessageEvent, times: Dict[str, Any] = RegexDict()):
    async with _group_lock(str(event.group_id)):
        await _handle_set_limit_times(event, times)


async def _handle_waifu_change(bot: Bot, event: GroupMessageEvent):
    gid = str(event.group_id)
    uid = str(event.user_id)
    today = str(datetime.date.today())
    group_record: Dict[str, Union[int, bool, Dict[str, Dict[str, int]]]] = get_group_record(gid)
    limit_times: int = group_record.setdefault('limit_times', default_limit_times)
    allow_change_waifu: bool = group_record.setdefault('allow_change_waifu', default_allow_change_waifu)
    if today not in group_record.keys() or uid not in group_record[today].keys():
        await today_waifu_change.finish('换老婆前请先娶个老婆哦，渣男', at_sender=True)
    if not allow_change_waifu:
        await today_waifu_change.finish('请专一的对待自己的老婆哦', at_sender=True)
    group_today_record: Dict[str, Dict[str, int]] = group_record[today]
    old_waifu_id: int = group_today_record[uid].get('waifu_id', 1234567)
    old_times: int = group_today_record[uid].setdefault('times', 0)
    members_by_id = {}
    if old_times >= limit_times or old_waifu_id == int(bot.self_id):
        new_waifu_id = -1
    else:
        try:
            all_member: list = await bot.get_group_member_list(group_id=gid)
        except Exception:
            await today_waifu_change.finish('群成员信息暂时不可用，请稍后再试')
        members_by_id = _member_map(all_member)
        id_set: Set[int] = set(i['user_id'] for i in all_member) - set(
            i['waifu_id'] for i in group_today_record.values()) - ban_id
        id_set.discard(int(uid))
        if id_set:
            new_waifu_id: int = random.choice(list(id_set))
        else:
            new_waifu_id: int = int(bot.self_id)
    group_today_record[uid] = {
        'waifu_id': new_waifu_id,
        'times': old_times if new_waifu_id == -1 else old_times + 1
    }
    save_group_record(gid, group_record)
    member_info = members_by_id.get(new_waifu_id, {})
    if not member_info and new_waifu_id not in (-1, int(bot.self_id)):
        try:
            member_info = await bot.get_group_member_info(group_id=gid, user_id=new_waifu_id)
        except Exception:
            member_info = {}
    message: Message = await construct_change_waifu_msg(member_info, new_waifu_id, int(bot.self_id), old_times,
                                                        limit_times)
    await today_waifu_change.finish(message, at_sender=True)


@today_waifu_change.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    async with _group_lock(str(event.group_id)):
        await _handle_waifu_change(bot, event)


async def _handle_today_waifu(bot: Bot, event: GroupMessageEvent):
    gid = str(event.group_id)
    uid = str(event.user_id)
    today = str(datetime.date.today())
    group_record: Dict[str, Union[int, bool, Dict[str, Dict[str, int]]]] = get_group_record(gid)
    limit_times: int = group_record.setdefault('limit_times', default_limit_times)
    allow_change_waifu: bool = group_record.setdefault('allow_change_waifu', default_allow_change_waifu)
    save = False
    is_first: bool
    waifu_id: int
    members_by_id = {}
    if today not in group_record.keys():
        group_record.clear()
        group_record['limit_times'] = limit_times
        group_record['allow_change_waifu'] = allow_change_waifu
        group_record[today] = {}
        save = True
    group_today_record: Dict[str, Dict[str, int]] = group_record[today]
    if uid in group_today_record.keys():
        waifu_id: int = group_today_record[uid].get('waifu_id', 1234567)
        is_first = False
    else:
        try:
            all_member: list = await bot.get_group_member_list(group_id=gid)
        except Exception:
            await today_waifu.finish('群成员信息暂时不可用，请稍后再试')
        members_by_id = _member_map(all_member)
        id_set: Set[int] = set(i['user_id'] for i in all_member) - set(
            i['waifu_id'] for i in group_today_record.values()) - ban_id
        id_set.discard(int(uid))
        if id_set:
            waifu_id: int = random.choice(list(id_set))
        else:
            waifu_id: int = int(bot.self_id)
        group_today_record[uid] = {
            'waifu_id': waifu_id,
            'times': 0,
        }
        save = True
        is_first = True
    if save:
        save_group_record(gid, group_record)
    member_info = members_by_id.get(waifu_id, {})
    if not member_info:
        try:
            member_info = await bot.get_group_member_info(group_id=gid, user_id=waifu_id)
        except Exception:
            member_info = {}
    message: Message = await construct_waifu_msg(member_info, waifu_id, int(bot.self_id), is_first)
    await today_waifu.finish(message, at_sender=True)


@today_waifu.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    async with _group_lock(str(event.group_id)):
        await _handle_today_waifu(bot, event)


async def _handle_waifu_refresh(event: GroupMessageEvent, name: Dict[str, Any]):
    plugin_name: str = name.get('name', __plugin_name__).strip()
    clear_group_record(str(event.group_id))
    await today_waifu_refresh.finish(f"{plugin_name}已刷新！")


@today_waifu_refresh.handle()
async def _(event: GroupMessageEvent, name: Dict[str, Any] = RegexDict()):
    async with _group_lock(str(event.group_id)):
        await _handle_waifu_refresh(event, name)


async def _handle_waifu_force(bot: Bot, event: GroupMessageEvent):
    gid = str(event.group_id)
    uid = str(event.user_id)
    today = str(datetime.date.today())

    at_segments = [seg for seg in event.message if seg.type == 'at']
    if not at_segments:
        await today_waifu_force.finish('请@你想强娶的对象', at_sender=True)

    target_id = int(at_segments[0].data['qq'])

    if target_id == int(uid):
        await today_waifu_force.finish('不能强娶自己哦', at_sender=True)
    if target_id in ban_id:
        await today_waifu_force.finish('该用户不可被娶', at_sender=True)
    try:
        member_info = await bot.get_group_member_info(group_id=gid, user_id=target_id)
    except Exception:
        await today_waifu_force.finish('该用户不在本群', at_sender=True)

    group_record: Dict[str, Union[int, bool, Dict[str, Dict[str, int]]]] = get_group_record(gid)
    limit_times: int = group_record.setdefault('limit_times', default_limit_times)
    allow_change_waifu: bool = group_record.setdefault('allow_change_waifu', default_allow_change_waifu)

    if today not in group_record:
        group_record.clear()
        group_record['limit_times'] = limit_times
        group_record['allow_change_waifu'] = allow_change_waifu
        group_record[today] = {}

    group_today_record: Dict[str, Dict[str, int]] = group_record[today]

    if uid in group_today_record and group_today_record[uid].get('force_married'):
        await today_waifu_force.finish('今天已经强娶过一次了哦', at_sender=True)

    for owner_uid, info in group_today_record.items():
        if info.get('waifu_id') == target_id and owner_uid != uid:
            try:
                owner_info = await bot.get_group_member_info(group_id=gid, user_id=int(owner_uid))
            except Exception:
                owner_info = {}
            message: Message = await construct_force_waifu_taken_msg(owner_info, owner_uid)
            await today_waifu_force.finish(message, at_sender=True)

    group_today_record[uid] = {
        'waifu_id': target_id,
        'times': limit_times,
        'force_married': True,
    }
    save_group_record(gid, group_record)

    message: Message = await construct_force_waifu_msg(member_info, target_id, int(bot.self_id))
    await today_waifu_force.finish(message, at_sender=True)


@today_waifu_force.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    async with _group_lock(str(event.group_id)):
        await _handle_waifu_force(bot, event)
