import os
import base64
import time
import hashlib
import asyncio
import subprocess
import httpx
import nonebot
from nonebot import on_fullmatch, on_startswith, require, get_driver, logger
from nonebot.message import event_preprocessor
from nonebot.permission import SUPERUSER
from nonebot.adapters import Bot as BaseBot, Event as BaseEvent
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, PrivateMessageEvent, MessageEvent
import json
from datetime import datetime, timezone, timedelta

from . import counter
from . import cache
from .charts import draw_pies_vstack, draw_summary, render_bot_cell, draw_grid

async def decimal_to_quaternary(decimal_num):
    if decimal_num == 0:
        return "0"    
    quaternary = ""
    num = decimal_num
    while num > 0:
        remainder = num % 4
        quaternary = str(remainder) + quaternary
        num = num // 4    
    return quaternary[::-1]

async def format_qq_data(data_list):   
    UTC_PLUS_8 = timezone(timedelta(hours=8))
    msg = []
    for user,bot in data_list:
        output_lines = []
        nickname = user.get('nickname', user.get('nick', 'N/A'))
        qq_number = user.get('uin', '0')
        reg_timestamp = user.get('reg_time', 0)
        reg_time = "未知"
        if reg_timestamp > 0:
            dt = datetime.fromtimestamp(reg_timestamp, tz=UTC_PLUS_8)
            reg_time = dt.strftime("%Y年%m月%d日 %H:%M:%S")
        qq_level = user.get('qqLevel', 0)
        qid = user.get('qid', 'N/A')
        is_vip = user.get('is_vip', False)
        vip_level = user.get('vip_level', 0)
        vip_info = ('\n' + f"是，VIP等级：{vip_level}") if is_vip else "否"
        output_lines.append(f"=== {nickname} ===")
        output_lines.append(f"-QQ号：{qq_number}")
        output_lines.append(f"-QID：{qid if len(qid) else '无'}")
        qq_level_signal = ['⭐', '🌙', '☀️', '👑', '🐧']
        qq_level_str2 = ''
        if qq_level == 0:
            qq_level = "未知"
        else:
            qq_level_str1 = await decimal_to_quaternary(qq_level)
            for i in range(len(qq_level_str1)):
                for j in range(int(qq_level_str1[i])):
                    qq_level_str2 += qq_level_signal[i]

        start_time = time.time()
        await bot.get_version_info()
        direct_delay = (time.time() - start_time) * 1000

        #output_lines.append(f"-注册时间：{reg_time}")
        output_lines.append(f"-QQ等级：{qq_level} {qq_level_str2[::-1]}".strip())
        output_lines.append(f"-是否为VIP及VIP等级：{vip_info}")
        output_lines.append(f"-连接延迟：{direct_delay:.2f}ms")
        msg.append({"type": "node", "data": {"name": nickname, "uin": qq_number, "content": '\n'.join(output_lines)}})
    return msg

#reloader = require('nonebot_plugin_reboot').Reloader
timing = require("nonebot_plugin_apscheduler").scheduler
#timing.add_job(reloader.reload, "cron", hour=23, minute=55, misfire_grace_time=3600, coalesce=True)

driver = get_driver()
@driver.on_bot_connect
async def remind(bot: Bot):
    return
    try:
        user_nick = await bot.get_group_member_info(group_id=961098542, user_id=bot.self_id)
        user_nick = (user_nick.get("card") or user_nick.get("nickname") or user_id)
        await bot.send_private_msg(user_id=864623174, message=f'{user_nick} 已上线！')
    except:
        return

airi_query_accounts = on_fullmatch('airiquery', priority=5, block=True, permission=SUPERUSER)
@airi_query_accounts.handle()
async def _(bot: Bot, ev: MessageEvent):
    qq_list = list(nonebot.get_bots().values())
    data_list = []
    for qq in qq_list:
        qqinfo = await bot.get_stranger_info(user_id=qq.self_id)
        data_list.append((qqinfo,qq))
    res = await format_qq_data(data_list)
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=res)


def _img_seg(png: bytes):
    return MessageSegment.image("base64://" + base64.b64encode(png).decode())


# QQ 默认头像的 md5,命中说明拿到的是占位图,降清晰度重试
_DEFAULT_AVATAR_MD5 = "acef72340ac0e914090bd35799f5594e"


async def _download_url(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        for _ in range(3):
            try:
                resp = await client.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                return resp.content
            except Exception:
                continue
    return b""


async def _user_avatar(uid: str) -> bytes:
    cached = cache.get("user_avatar", uid, ttl=cache.TTL_AVATAR)
    if cached:
        return cached
    url = f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=640"
    data = await _download_url(url)
    if not data or hashlib.md5(data).hexdigest() == _DEFAULT_AVATAR_MD5:
        data = await _download_url(f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100")
    if data:
        cache.put("user_avatar", uid, data)
    return data


async def _group_avatar(gid: str) -> bytes:
    cached = cache.get("group_avatar", gid, ttl=cache.TTL_AVATAR)
    if cached:
        return cached
    data = await _download_url(f"http://p.qlogo.cn/gh/{gid}/{gid}/640")
    if data:
        cache.put("group_avatar", gid, data)
    return data


async def _prefetch_avatars(user_ids, group_ids) -> dict:
    """并发下载用户+群头像,返回 {id: bytes}(私聊/失败为空 bytes)。"""
    ids = [u for u in dict.fromkeys(user_ids) if u]
    gids = [g for g in dict.fromkeys(group_ids) if g and g != counter.PRIVATE_KEY]
    tasks = [_user_avatar(u) for u in ids] + [_group_avatar(g) for g in gids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = {}
    for key, res in zip(ids + gids, results):
        out[key] = res if isinstance(res, (bytes, bytearray)) else b""
    return out


async def _bot_nick(bot: Bot, self_id: str) -> str:
    cached = cache.get("bot_name", self_id, ttl=cache.TTL_NAME)
    if cached:
        return cached
    try:
        info = await bot.get_stranger_info(user_id=int(self_id))
        nick = info.get("nickname") or info.get("nick")
        if nick:
            cache.put("bot_name", self_id, nick)
            return nick
    except Exception:
        pass
    # 拿不到就退回旧缓存(不判过期),再退回 self_id
    return cache.get("bot_name", self_id) or self_id


async def _group_labeler(bot: Bot, sessions):
    """预取本次涉及的群名,返回 label_of(会话id)->(第一行, 第二行)。
    群:第一行群名(写不下由绘图层省略),第二行'（群号）：数字'灰字;私聊只有一行。"""
    names = {}
    for sid in sessions:
        if sid == counter.PRIVATE_KEY:
            continue
        cached = cache.get("group_name", sid, ttl=cache.TTL_NAME)
        if cached:
            names[sid] = cached
            continue
        try:
            info = await bot.get_group_info(group_id=int(sid))
            gname = info.get("group_name") or ""
            if gname:
                cache.put("group_name", sid, gname)
            # 群名拿不到时退回旧缓存(不判过期),仍拿不到给空串
            names[sid] = gname or cache.get("group_name", sid) or ""
        except Exception:
            names[sid] = cache.get("group_name", sid) or ""

    def label_of(sid):
        if sid == counter.PRIVATE_KEY:
            return ("私聊", "")
        gname = names.get(sid) or f"群{sid}"
        return (gname, f"群号：{sid}")

    return label_of


async def _bot_pies(bot: Bot, self_id: str, data: dict, avatars: dict = None) -> bytes:
    """给一个 bot 生成收/发上下拼接的单张饼图 png(带参分支用)。"""
    avatars = avatars or {}
    recv = data.get("recv", {})
    sent = data.get("sent", {})
    label_of = await _group_labeler(bot, set(recv) | set(sent))
    recv_total = sum(recv.values())
    sent_total = sum(sent.values())
    return draw_pies_vstack(
        (f"收 · 共 {recv_total} 条", recv),
        (f"发 · 共 {sent_total} 条", sent),
        label_of=label_of,
        avatar_of=lambda sid: avatars.get(sid),
    )


async def _bot_cell(bot: Bot, self_id: str, nick: str, data: dict, avatars: dict = None):
    """给一个 bot 生成网格单元格 Image(顶部昵称+头像 + 收/发饼图)。"""
    avatars = avatars or {}
    recv = data.get("recv", {})
    sent = data.get("sent", {})
    label_of = await _group_labeler(bot, set(recv) | set(sent))
    recv_total = sum(recv.values())
    sent_total = sum(sent.values())
    return render_bot_cell(
        f"{nick}({self_id})",
        (f"收 · 共 {recv_total} 条", recv),
        (f"发 · 共 {sent_total} 条", sent),
        label_of=label_of,
        avatar_of=lambda sid: avatars.get(sid),
        header_avatar=avatars.get(self_id),
    )


airi_analysis = on_startswith('airianalysis', priority=5, block=True, permission=SUPERUSER)
@airi_analysis.handle()
async def _(bot: Bot, ev: MessageEvent):
    if not isinstance(ev, GroupMessageEvent):
        await airi_analysis.finish('请在群里使用 airianalysis')

    arg = ev.get_plaintext().removeprefix('airianalysis').strip()
    stats = counter.get_stats()
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')

    # 带参:只发指定 bot 的收/发饼图,直接发送
    if arg:
        data = stats.get(arg)
        if not data:
            await airi_analysis.finish(f'今日({today})没有 bot {arg} 的收发记录')
        nick = await _bot_nick(bot, arg)
        groups = set(data.get('recv', {})) | set(data.get('sent', {}))
        avatars = await _prefetch_avatars([], groups)
        pie = await _bot_pies(bot, arg, data, avatars)
        cache.flush()
        msg = Message(f'📊 {nick}({arg}) · {today}\n') + _img_seg(pie)
        await bot.send_group_msg(group_id=ev.group_id, message=msg)
        return

    # 无参: 2张图 —— ①所有 bot 图表拼成网格(每行4个) ②跨 bot 汇总总表
    if not stats:
        await airi_analysis.finish(f'今日({today})暂无收发统计')

    bots = nonebot.get_bots()
    # 预下载所有涉及的 bot 头像 + 群头像(去重并发)
    all_groups = set()
    for data in stats.values():
        all_groups |= set(data.get('recv', {})) | set(data.get('sent', {}))
    avatars = await _prefetch_avatars(list(stats.keys()), all_groups)

    bot_totals = []
    cells = []
    for self_id, data in stats.items():
        cur = bots.get(self_id, bot)  # 优先用对应 bot 拿群名,离线则借当前 bot
        nick = await _bot_nick(cur, self_id)
        recv_total = sum(data.get('recv', {}).values())
        sent_total = sum(data.get('sent', {}).values())
        bot_totals.append((nick, self_id, recv_total, sent_total, avatars.get(self_id)))
        try:
            cells.append(await _bot_cell(cur, self_id, nick, data, avatars))
        except Exception as e:
            logger.opt(colors=True).warning(f'<y>airianalysis 生成 {self_id} 单元格失败: {e}</y>')

    grid = draw_grid(cells, cols=4)
    summary = draw_summary(bot_totals)

    cache.flush()
    await airi_analysis.finish(_img_seg(grid)+_img_seg(summary), reply_message=True)


REBOOT_CMD = (
    '/usr/bin/screen -S airicore -X quit; '
    '/bin/bash -c "cd /root/airi/airicore && /usr/bin/screen -dmS airicore ./launch.sh"'
)

airi_force_reboot = on_fullmatch('force-reboot', priority=5, block=True, permission=SUPERUSER)
@airi_force_reboot.handle()
async def _(bot: Bot, ev: PrivateMessageEvent):
    # Detach fully from the python parent process: start_new_session puts the child
    # in its own session/process group so it survives when this process is killed.
    subprocess.Popen(
        REBOOT_CMD,
        shell=True,
        executable='/bin/bash',
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


airi_reboot = on_fullmatch('reboot', priority=5, block=True, permission=SUPERUSER)
@airi_reboot.handle()
async def _(bot: Bot, ev: PrivateMessageEvent):
    # Send Ctrl+C (\003) to the airicore screen session so it can shut down
    # gracefully; the launch script / process manager handles the restart.
    subprocess.Popen(
        ['/usr/bin/screen', '-S', 'airicore', '-X', 'stuff', '\003'],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
