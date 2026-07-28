import os
import re
import base64
import shutil
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
from . import ram_inspector
from .charts import draw_pies_vstack, draw_summary, render_bot_cell, draw_grid

def decimal_to_quaternary(decimal_num: int) -> str:
    if decimal_num <= 0:
        return "0"
    digits = []
    num = decimal_num
    while num > 0:
        digits.append(str(num % 4))
        num //= 4
    return "".join(digits)


_QQ_LEVEL_SIGNALS = ['⭐', '🌙', '☀️', '👑', '🐧']
_QQ_LEVEL_MAX_SYMBOLS = 60


def build_qq_level_signal(qq_level: int) -> str:
    if qq_level <= 0:
        return ""
    top = len(_QQ_LEVEL_SIGNALS) - 1
    remain = qq_level
    counts = [0] * len(_QQ_LEVEL_SIGNALS)
    counts[top] = remain // (4 ** top)
    remain -= counts[top] * (4 ** top)
    for i in range(top - 1, -1, -1):
        counts[i] = remain // (4 ** i)
        remain -= counts[i] * (4 ** i)
    parts = []
    total = 0
    for i in range(top, -1, -1):
        n = counts[i]
        if total + n > _QQ_LEVEL_MAX_SYMBOLS:
            n = max(0, _QQ_LEVEL_MAX_SYMBOLS - total)
        total += n
        parts.append(_QQ_LEVEL_SIGNALS[i] * n)
    return "".join(parts)

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
        try:
            qq_level_int = int(qq_level)
        except (TypeError, ValueError):
            qq_level_int = 0
        qq_level_str2 = build_qq_level_signal(qq_level_int)
        qq_level_disp = "未知" if qq_level_int <= 0 else qq_level_int

        start_time = time.time()
        try:
            await bot.get_version_info()
            direct_delay = (time.time() - start_time) * 1000
        except Exception:
            direct_delay = -1

        output_lines.append(f"-QQ等级：{qq_level_disp} {qq_level_str2}".strip())
        output_lines.append(f"-是否为VIP及VIP等级：{vip_info}")
        delay_text = "获取失败" if direct_delay < 0 else f"{direct_delay:.2f}ms"
        output_lines.append(f"-连接延迟：{delay_text}")
        msg.append({"type": "node", "data": {"name": nickname, "uin": qq_number, "content": '\n'.join(output_lines)}})
    return msg

timing = require("nonebot_plugin_apscheduler").scheduler

driver = get_driver()

airi_query_accounts = on_fullmatch('airiquery', priority=5, block=True, permission=SUPERUSER)
@airi_query_accounts.handle()
async def _(bot: Bot, ev: MessageEvent):
    qq_list = list(nonebot.get_bots().values())
    data_list = []
    for qq in qq_list:
        qqinfo = await bot.get_stranger_info(user_id=qq.self_id)
        data_list.append((qqinfo,qq))
    res = await format_qq_data(data_list)
    if isinstance(ev, GroupMessageEvent):
        await bot.send_group_forward_msg(group_id=ev.group_id, messages=res)
    else:
        await bot.send_private_forward_msg(user_id=ev.user_id, messages=res)


def _img_seg(png: bytes):
    return MessageSegment.image("base64://" + base64.b64encode(png).decode())


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
    return cache.get("bot_name", self_id) or self_id


async def _group_labeler(bot: Bot, sessions):
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
            names[sid] = gname or cache.get("group_name", sid) or ""
        except Exception:
            names[sid] = cache.get("group_name", sid) or ""

    def label_of(sid):
        if sid == counter.PRIVATE_KEY:
            return ("私聊", "")
        gname = names.get(sid) or f"群{sid}"
        return (gname, f"群号：{sid}")

    return label_of


async def _bot_pies(bot: Bot, self_id: str, data: dict, avatars: dict = None, date_text: str = "") -> bytes:
    avatars = avatars or {}
    recv = data.get("recv", {})
    sent = data.get("sent", {})
    label_of = await _group_labeler(bot, set(recv) | set(sent))
    recv_total = sum(recv.values())
    sent_total = sum(sent.values())
    return await asyncio.to_thread(
        draw_pies_vstack,
        (f"收 · 共 {recv_total} 条", recv),
        (f"发 · 共 {sent_total} 条", sent),
        label_of,
        lambda sid: avatars.get(sid),
        date_text,
    )


async def _bot_cell(bot: Bot, self_id: str, nick: str, data: dict, avatars: dict = None):
    avatars = avatars or {}
    recv = data.get("recv", {})
    sent = data.get("sent", {})
    label_of = await _group_labeler(bot, set(recv) | set(sent))
    recv_total = sum(recv.values())
    sent_total = sum(sent.values())
    return await asyncio.to_thread(
        render_bot_cell,
        f"{nick}({self_id})",
        (f"收 · 共 {recv_total} 条", recv),
        (f"发 · 共 {sent_total} 条", sent),
        label_of,
        lambda sid: avatars.get(sid),
        avatars.get(self_id),
    )


airi_analysis = on_startswith('airianalysis', priority=5, block=True, permission=SUPERUSER)
@airi_analysis.handle()
async def _(bot: Bot, ev: MessageEvent):
    if not isinstance(ev, GroupMessageEvent):
        await airi_analysis.finish('请在群里使用 airianalysis')

    arg = ev.get_plaintext().removeprefix('airianalysis').strip()
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')

    day = today
    bot_id = ''
    for tok in arg.split():
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', tok):
            day = tok
        elif tok:
            bot_id = tok

    stats = counter.get_stats(day)

    if bot_id:
        data = stats.get(bot_id)
        if not data:
            days = counter.get_available_days()
            tip = f'\n可用日期：{"、".join(days)}' if days else ''
            await airi_analysis.finish(f'{day} 没有 bot {bot_id} 的收发记录{tip}')
        nick = await _bot_nick(bot, bot_id)
        groups = set(data.get('recv', {})) | set(data.get('sent', {}))
        avatars = await _prefetch_avatars([], groups)
        pie = await _bot_pies(bot, bot_id, data, avatars, date_text=day)
        cache.flush()
        msg = Message(f'{nick}({bot_id}) · {day}\n') + _img_seg(pie)
        await bot.send_group_msg(group_id=ev.group_id, message=msg)
        return

    if not stats:
        days = counter.get_available_days()
        tip = f'\n可用日期：{"、".join(days)}' if days else ''
        await airi_analysis.finish(f'{day} 暂无收发统计{tip}')

    bots = nonebot.get_bots()
    all_groups = set()
    for data in stats.values():
        all_groups |= set(data.get('recv', {})) | set(data.get('sent', {}))
    avatars = await _prefetch_avatars(list(stats.keys()), all_groups)

    bot_totals = []
    cells = []
    for self_id, data in stats.items():
        cur = bots.get(self_id, bot)
        nick = await _bot_nick(cur, self_id)
        recv_total = sum(data.get('recv', {}).values())
        sent_total = sum(data.get('sent', {}).values())
        bot_totals.append((nick, self_id, recv_total, sent_total, avatars.get(self_id)))
        try:
            cells.append(await _bot_cell(cur, self_id, nick, data, avatars))
        except Exception as e:
            logger.opt(colors=True).warning(f'<y>airianalysis 生成 {self_id} 单元格失败: {e}</y>')

    grid = await asyncio.to_thread(draw_grid, cells, 4, day)
    summary = await asyncio.to_thread(draw_summary, bot_totals, day)

    cache.flush()
    await airi_analysis.finish(_img_seg(grid)+_img_seg(summary), reply_message=True)


SCREEN_BIN = shutil.which('screen') or '/usr/bin/screen'
SCREEN_SESSION = str(getattr(driver.config, 'reboot_screen_session', '') or 'airicore')
AIRICORE_DIR = str(getattr(driver.config, 'reboot_workdir', '') or os.getcwd())
BASH_BIN = shutil.which('bash') or '/bin/bash'

REBOOT_CMD = (
    f'{SCREEN_BIN} -S {SCREEN_SESSION} -X quit; '
    f'{BASH_BIN} -c "cd {AIRICORE_DIR} && {SCREEN_BIN} -dmS {SCREEN_SESSION} ./launch.sh"'
)


def _reboot_preflight() -> str:
    if os.name == 'nt':
        return '重启指令依赖 screen，Windows 环境不支持，请手动重启。'
    if not os.path.isfile(SCREEN_BIN):
        return f'未找到 screen（{SCREEN_BIN}），无法执行重启，请手动重启。'
    if not os.path.isdir(AIRICORE_DIR):
        return f'工作目录不存在（{AIRICORE_DIR}），请配置 reboot_workdir。'
    return ''


airi_force_reboot = on_fullmatch('force-reboot', priority=5, block=True, permission=SUPERUSER)
@airi_force_reboot.handle()
async def _(bot: Bot, ev: MessageEvent):
    err = _reboot_preflight()
    if err:
        await airi_force_reboot.finish(err)
    try:
        subprocess.Popen(
            REBOOT_CMD,
            shell=True,
            executable=BASH_BIN,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as e:
        await airi_force_reboot.finish(f'强制重启失败: {e}')
    await airi_force_reboot.send('已发出强制重启指令，AiriCore 即将重启。')


airi_reboot = on_fullmatch('reboot', priority=5, block=True, permission=SUPERUSER)
@airi_reboot.handle()
async def _(bot: Bot, ev: MessageEvent):
    err = _reboot_preflight()
    if err:
        await airi_reboot.finish(err)
    try:
        subprocess.Popen(
            [SCREEN_BIN, '-S', SCREEN_SESSION, '-X', 'stuff', '\003'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as e:
        await airi_reboot.finish(f'重启失败: {e}')
    await airi_reboot.send('已发出重启指令，AiriCore 即将重启。')


def _format_bytes(b: int) -> str:
    if b < 1024:
        return f"{b}B"
    kb = b / 1024
    if kb < 1024:
        return f"{kb:.1f}KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f}MB"
    gb = mb / 1024
    return f"{gb:.2f}GB"


def _ram_node(bot_id: str, name: str, content: str) -> dict:
    return {"type": "node", "data": {"name": name, "uin": bot_id, "content": content}}


airi_ram = on_fullmatch('airiram', priority=5, block=True, permission=SUPERUSER)
@airi_ram.handle()
async def _(bot: Bot, ev: MessageEvent):
    if not isinstance(ev, GroupMessageEvent):
        await airi_ram.finish('请在群里使用 airiram')

    process_mem, mode, inspections = ram_inspector.inspect_all()
    bot_id = str(bot.self_id)

    mode_desc = {
        "ram": "全驻留内存，最快，内存占用最高",
        "balanced": "仅缓存高频文件，平衡模式",
        "disk": "完全停用缓存，每次读盘，内存最小",
    }

    total_disk = sum(i["disk_bytes"] for i in inspections)
    total_ram = sum(i["ram_bytes"] for i in inspections)

    overview = ["=== 概览 ==="]
    if process_mem > 0:
        overview.append(f"Bot 进程内存占用: {_format_bytes(process_mem)}")
    else:
        overview.append("Bot 进程内存占用: 无法获取 (需安装 psutil)")
    overview.append(f"当前缓存模式: {mode}")
    if mode in mode_desc:
        overview.append(mode_desc[mode])
    overview.append("")
    overview.append(f"磁盘缓存合计: {_format_bytes(total_disk)}")
    overview.append(f"内存缓存合计: {_format_bytes(total_ram)}")
    if mode == "disk":
        overview.append("注: disk 模式下内存缓存已停用")

    nodes = [_ram_node(bot_id, "概览", "\n".join(overview))]

    for info in inspections:
        lines = [f"=== {info['name']} ==="]
        lines.append(f"磁盘: {_format_bytes(info['disk_bytes'])}")
        lines.append(f"内存: {_format_bytes(info['ram_bytes'])}")
        if info.get("error"):
            lines.append(f"读取失败: {info['error']}")
        elif info["details"]:
            lines.append("缓存明细:")
            for d in info["details"]:
                lines.append(f"  - {d}")
        else:
            lines.append("缓存明细: 暂无缓存内容")
        nodes.append(_ram_node(bot_id, info["name"], "\n".join(lines)))

    await bot.send_group_forward_msg(group_id=ev.group_id, messages=nodes, _timeout=120)
