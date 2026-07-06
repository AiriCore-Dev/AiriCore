# -*- coding: utf-8 -*-
"""airi_bilibili_post —— B 站订阅推送插件。

在 QQ 群内订阅 B 站 UP 主的「动态」或「直播间」，插件定时轮询，
一旦有新动态发布或开播，就把消息推送到订阅了该 UP 的群里。

命令（需群管理/群主/超管权限来增删订阅，查询无需权限）：
  订阅动态 <UID>      在本群订阅该 UP 的动态更新
  订阅直播 <UID>      在本群订阅该 UP 的开播提醒
  取消动态 <UID>      取消本群对该 UP 的动态订阅
  取消直播 <UID>      取消本群对该 UP 的开播订阅
  b站订阅列表         查看本群所有订阅
  b站帮助             查看帮助

数据结构（data.pk）：
  {
    "subs": { uid(int): {"name": str,
                         "dynamic_groups": set[int],
                         "live_groups": set[int]} },
    "live_status": { uid(int): int },      # 上次已知直播状态，用于检测开播沿
    "last_dynamic": { uid(int): str },     # 上次已推送的最新动态 id
    "dynamic_bootstrapped": set[int],      # 已完成动态基线初始化的 uid
    "group_bot": { group_id(int): str },   # 群 -> 负责推送的 bot self_id（挂多个 bot 时用）
  }
"""
import os
import gc
import pickle

import httpx
import nonebot
from nonebot import get_driver, on_startswith, on_fullmatch, require
from nonebot.permission import SUPERUSER
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER

from . import data_source as ds

timings = require("nonebot_plugin_apscheduler").scheduler
driver = get_driver()

# 可选：在 .env 里配置 bilibili_cookie（含 SESSDATA）以稳定拉取动态
BILI_COOKIE = getattr(driver.config, "bilibili_cookie", "")

DATA_DIR = os.path.join("data", "airi_bilibili_post")
DATA_FILE = os.path.join(DATA_DIR, "data.pk")

MANAGE_PERM = GROUP_ADMIN | GROUP_OWNER | SUPERUSER

data = {
    "subs": {},
    "live_status": {},
    "last_dynamic": {},
    "dynamic_bootstrapped": set(),
    "group_bot": {},
}


# --------------------------------------------------------------------------- #
# 持久化
# --------------------------------------------------------------------------- #
@driver.on_startup
async def load_data():
    global data
    try:
        with open(DATA_FILE, "rb") as f:
            loaded = pickle.load(f)
        # 补齐缺失的顶层键，兼容旧存档
        for k, default in (
            ("subs", {}),
            ("live_status", {}),
            ("last_dynamic", {}),
            ("dynamic_bootstrapped", set()),
            ("group_bot", {}),
        ):
            loaded.setdefault(k, default)
        data = loaded
    except FileNotFoundError:
        os.makedirs(DATA_DIR, exist_ok=True)
        await save_data()
    except Exception as e:
        logger.warning(f"[bilibili_post] 读取存档失败，使用空数据：{e!r}")
        os.makedirs(DATA_DIR, exist_ok=True)


@driver.on_shutdown
async def save_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "wb") as f:
        pickle.dump(data, f)


timings.add_job(save_data, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _sub_of(uid: int) -> dict:
    """取得（必要时创建）某 uid 的订阅记录。"""
    sub = data["subs"].get(uid)
    if sub is None:
        sub = {"name": str(uid), "dynamic_groups": set(), "live_groups": set()}
        data["subs"][uid] = sub
    return sub


def _cleanup_uid(uid: int):
    """当某 uid 不再被任何群订阅时，清掉它的全部状态。"""
    sub = data["subs"].get(uid)
    if sub and not sub["dynamic_groups"] and not sub["live_groups"]:
        data["subs"].pop(uid, None)
        data["live_status"].pop(uid, None)
        data["last_dynamic"].pop(uid, None)
        data["dynamic_bootstrapped"].discard(uid)


def _purge_group(gid: int):
    """把某个群从所有订阅中彻底移除（bot 被踢出群时调用）。"""
    gid = int(gid)
    for uid in list(data["subs"].keys()):
        sub = data["subs"][uid]
        sub["dynamic_groups"].discard(gid)
        sub["live_groups"].discard(gid)
        _cleanup_uid(uid)
    data["group_bot"].pop(gid, None)
    logger.warning(f"[bilibili_post] 已从群 {gid} 移除全部订阅（bot 不在该群）")


def _parse_uid(arg: str) -> int:
    """从命令参数里解析 UID，非法返回 0。支持纯数字或空间链接。"""
    arg = arg.strip()
    if arg.isdigit():
        return int(arg)
    # 从 space.bilibili.com/xxx 里抠数字
    import re
    m = re.search(r"space\.bilibili\.com/(\d+)", arg)
    if m:
        return int(m.group(1))
    m = re.search(r"\d+", arg)
    return int(m.group(0)) if m else 0


def _is_not_in_group(e: Exception) -> bool:
    """判断异常是否为“bot 已不在该群”（被踢/退群）。"""
    if not isinstance(e, ActionFailed):
        return False
    # OneBot 实现的错误码/文案不统一，两头都判
    retcode = e.info.get("retcode") if hasattr(e, "info") else None
    msg = str(e.info.get("wording", "")) + str(e.info.get("message", "")) if hasattr(e, "info") else str(e)
    if retcode == 110:
        return True
    return ("移出该群" in msg) or ("不是群成员" in msg) or ("请重新加群" in msg)


def _record_group_bot(gid, bot):
    """登记某群由哪个 bot 负责推送。订阅命令触发时调用。"""
    data["group_bot"][int(gid)] = str(bot.self_id)


def _bot_for_group(gid):
    """解析负责某群的 bot。

    返回 (bot, authoritative)：
      · 有登记且该 bot 在线   -> (bot, True)   权威，推送失败若判定踢群可清理
      · 有登记但该 bot 离线   -> (None, False)  跳过本轮，不清理（可能只是临时掉线）
      · 无登记（旧存档/历史） -> (任一在线 bot, False) 猜测发送，成功后自愈登记，失败不清理
      · 无任何在线 bot        -> (None, False)
    """
    online = nonebot.get_bots()
    if not online:
        return None, False
    preferred = data["group_bot"].get(int(gid))
    if preferred is not None:
        bot = online.get(str(preferred))
        return (bot, True) if bot is not None else (None, False)
    # 无登记：回退任一在线 bot，仅作猜测
    return next(iter(online.values())), False


async def _push_to_groups(group_ids, message, *, fallback=None):
    """把消息推送到给定群列表；单群失败不影响其它群。

    每个群用它登记的 bot 推送（挂多个 bot 时避免用错 bot）。
    fallback：带图消息发送失败（多为 QQ 客户端富媒体传输失败）时改发的纯文字消息，
    保证通知不因图片问题而整条丢失。
    仅当用「权威 bot」（该群登记且在线）推送仍被判定踢群时，才清理该群订阅。
    """
    if not nonebot.get_bots():
        return
    dirty = False
    for gid in list(group_ids):
        bot, authoritative = _bot_for_group(gid)
        if bot is None:
            # 登记的 bot 掉线：跳过本轮，等它上线再推，不误删订阅
            continue
        try:
            await bot.send_group_msg(group_id=int(gid), message=message)
            if not authoritative:
                # 猜测发送成功 -> 自愈登记，下次直接用它
                _record_group_bot(gid, bot)
                dirty = True
        except Exception as e:
            if _is_not_in_group(e) and authoritative:
                _purge_group(gid)
                dirty = True
                continue
            if _is_not_in_group(e):
                # 非权威 bot 猜错群，不清理，仅记日志
                logger.warning(f"[bilibili_post] 群 {gid} 无登记 bot 且猜测 bot 不在该群，跳过")
                continue
            logger.warning(f"[bilibili_post] 推送到群 {gid} 失败：{e!r}")
            if fallback is not None:
                try:
                    await bot.send_group_msg(group_id=int(gid), message=fallback)
                    if not authoritative:
                        _record_group_bot(gid, bot)
                        dirty = True
                except Exception as e2:
                    if _is_not_in_group(e2) and authoritative:
                        _purge_group(gid)
                        dirty = True
                        continue
                    logger.warning(f"[bilibili_post] 纯文字兜底也失败 群 {gid}：{e2!r}")
    if dirty:
        await save_data()


async def _image_seg(url):
    """把远程图片下成 base64 再包成图片段，避免客户端拉图失败。拿不到返回 None。"""
    if not url:
        return None
    b64 = await ds.fetch_image_b64(url)
    if not b64:
        return None
    try:
        return MessageSegment.image("base64://" + b64)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# 订阅命令
# --------------------------------------------------------------------------- #
sub_dynamic = on_startswith("订阅动态", priority=5, block=True, permission=MANAGE_PERM)
sub_live = on_startswith("订阅直播", priority=5, block=True, permission=MANAGE_PERM)
unsub_dynamic = on_startswith("取消动态", priority=5, block=True, permission=MANAGE_PERM)
unsub_live = on_startswith("取消直播", priority=5, block=True, permission=MANAGE_PERM)
sub_list = on_fullmatch(("b站订阅列表", "B站订阅列表", "订阅列表"), priority=5, block=True)
bili_help = on_fullmatch(("b站帮助", "B站帮助", "bili帮助"), priority=5, block=True)


@sub_dynamic.handle()
async def _(bot: Bot, ev: GroupMessageEvent):
    uid = _parse_uid(ev.get_plaintext()[4:])
    if not uid:
        await sub_dynamic.finish("💫 用法：订阅动态 <UID>", reply_message=True)
    gid = ev.group_id
    sub = _sub_of(uid)
    if gid in sub["dynamic_groups"]:
        await sub_dynamic.finish(f"❌ 本群已订阅 UID {uid} 的动态。", reply_message=True)
    # 拉一次昵称，顺便验证 uid 有效性
    async with httpx.AsyncClient() as client:
        name = await ds.get_user_name(client, uid, BILI_COOKIE)
    if name:
        sub["name"] = name
    sub["dynamic_groups"].add(gid)
    _record_group_bot(gid, bot)  # 收到本群消息的这个 bot 即负责该群推送
    # 首次订阅先建立基线，避免把历史动态当新动态推一遍
    if uid not in data["dynamic_bootstrapped"]:
        try:
            async with httpx.AsyncClient() as client:
                dyns = await ds.get_user_dynamics(client, uid, BILI_COOKIE)
            if dyns:
                data["last_dynamic"][uid] = dyns[0]["id"]
        except Exception as e:
            logger.warning(f"[bilibili_post] 动态基线初始化失败 uid={uid}: {e!r}")
        data["dynamic_bootstrapped"].add(uid)
    await save_data()
    await sub_dynamic.finish(f"✅ 已订阅 {sub['name']}（UID {uid}）的动态更新。", reply_message=True)


@sub_live.handle()
async def _(bot: Bot, ev: GroupMessageEvent):
    uid = _parse_uid(ev.get_plaintext()[4:])
    if not uid:
        await sub_live.finish("💫 用法：订阅直播 <UID>", reply_message=True)
    gid = ev.group_id
    sub = _sub_of(uid)
    if gid in sub["live_groups"]:
        await sub_live.finish(f"❌ 本群已订阅 UID {uid} 的直播。", reply_message=True)
    # 拉一次直播状态，顺便拿昵称并建立基线
    try:
        async with httpx.AsyncClient() as client:
            status = await ds.get_live_status(client, [uid], BILI_COOKIE)
        info = status.get(uid)
        if info:
            if info.get("uname"):
                sub["name"] = info["uname"]
            data["live_status"][uid] = info["live_status"]
    except Exception as e:
        logger.warning(f"[bilibili_post] 直播基线初始化失败 uid={uid}: {e!r}")
    sub["live_groups"].add(gid)
    _record_group_bot(gid, bot)  # 收到本群消息的这个 bot 即负责该群推送
    await save_data()
    await sub_live.finish(f"✅ 已订阅 {sub['name']}（UID {uid}）的开播提醒。", reply_message=True)


@unsub_dynamic.handle()
async def _(bot: Bot, ev: GroupMessageEvent):
    uid = _parse_uid(ev.get_plaintext()[4:])
    if not uid:
        await unsub_dynamic.finish("💫 用法：取消动态 <UID>", reply_message=True)
    sub = data["subs"].get(uid)
    if not sub or ev.group_id not in sub["dynamic_groups"]:
        await unsub_dynamic.finish(f"❌ 本群未订阅 UID {uid} 的动态。", reply_message=True)
    sub["dynamic_groups"].discard(ev.group_id)
    name = sub["name"]
    _cleanup_uid(uid)
    await save_data()
    await unsub_dynamic.finish(f"✅ 已取消 {name}（UID {uid}）的动态订阅。", reply_message=True)


@unsub_live.handle()
async def _(bot: Bot, ev: GroupMessageEvent):
    uid = _parse_uid(ev.get_plaintext()[4:])
    if not uid:
        await unsub_live.finish("💫 用法：取消直播 <UID>", reply_message=True)
    sub = data["subs"].get(uid)
    if not sub or ev.group_id not in sub["live_groups"]:
        await unsub_live.finish(f"❌ 本群未订阅 UID {uid} 的直播。", reply_message=True)
    sub["live_groups"].discard(ev.group_id)
    name = sub["name"]
    _cleanup_uid(uid)
    await save_data()
    await unsub_live.finish(f"✅ 已取消 {name}（UID {uid}）的开播订阅。", reply_message=True)


@sub_list.handle()
async def _(bot: Bot, ev: GroupMessageEvent):
    gid = ev.group_id
    dyn_lines, live_lines = [], []
    for uid, sub in data["subs"].items():
        if gid in sub["dynamic_groups"]:
            dyn_lines.append(f" · {sub['name']}（UID {uid}）")
        if gid in sub["live_groups"]:
            live_lines.append(f" · {sub['name']}（UID {uid}）")
    if not dyn_lines and not live_lines:
        await sub_list.finish("📭 本群暂无 B 站订阅。", reply_message=True)
    res = "📋 本群 B 站订阅列表\n\n📢 动态订阅：\n"
    res += ("\n".join(dyn_lines) if dyn_lines else " （无）")
    res += "\n\n🔴 直播订阅：\n"
    res += ("\n".join(live_lines) if live_lines else " （无）")
    await sub_list.finish(res, reply_message=True)


@bili_help.handle()
async def _(bot: Bot, ev: GroupMessageEvent):
    res = (
        "🅱️ Bilibili订阅推送\n\n"
        "📒 指令列表：\n"
        " · 订阅动态 <UID>：订阅该 UP 的动态更新（管理）\n"
        " · 订阅直播 <UID>：订阅该 UP 的开播提醒（管理）\n"
        " · 取消动态 <UID>：取消动态订阅（管理）\n"
        " · 取消直播 <UID>：取消开播订阅（管理）\n"
        " · b站订阅列表：查看本群订阅\n"
        " · b站帮助：查看本帮助\n\n"
        "💡 UID 为 UP 主空间号，可直接填数字或粘贴空间链接。\n"
        "订阅/取消需要群管理员、群主或超管权限。"
    )
    await bili_help.finish(res, reply_message=True)


# --------------------------------------------------------------------------- #
# 定时轮询
# --------------------------------------------------------------------------- #
async def check_live():
    """轮询所有被订阅了直播的 UP，检测“未开播->开播”的上升沿并推送。"""
    uids = [uid for uid, s in data["subs"].items() if s["live_groups"]]
    if not uids:
        return
    try:
        async with httpx.AsyncClient() as client:
            status = await ds.get_live_status(client, uids, BILI_COOKIE)
    except Exception as e:
        logger.warning(f"[bilibili_post] 直播状态轮询失败：{e!r}")
        return

    for uid in uids:
        info = status.get(uid)
        if not info:
            continue
        prev = data["live_status"].get(uid, 0)
        cur = info["live_status"]
        data["live_status"][uid] = cur
        sub = data["subs"].get(uid)
        if not sub:
            continue
        if info.get("uname"):
            sub["name"] = info["uname"]
        # 只在 1(直播中) 的上升沿推送
        if cur == 1 and prev != 1:
            room_id = info["room_id"]
            title = info["title"] or "（无标题）"
            text = (
                f"🔴 {sub['name']} 开播啦！\n"
                f"📺 {title}\n"
                f"🔗 https://live.bilibili.com/{room_id}"
            )
            msg = Message(text)
            seg = await _image_seg(info.get("cover"))
            if seg is not None:
                msg += seg
            await _push_to_groups(sub["live_groups"], msg, fallback=Message(text))


async def check_dynamic():
    """轮询所有被订阅了动态的 UP，推送新动态。"""
    uids = [uid for uid, s in data["subs"].items() if s["dynamic_groups"]]
    if not uids:
        return
    for uid in uids:
        sub = data["subs"].get(uid)
        if not sub:
            continue
        try:
            async with httpx.AsyncClient() as client:
                dyns = await ds.get_user_dynamics(client, uid, BILI_COOKIE)
        except Exception as e:
            logger.warning(f"[bilibili_post] 动态轮询失败 uid={uid}: {e!r}")
            continue
        if not dyns:
            continue

        last_id = data["last_dynamic"].get(uid)
        # 从未记录过 -> 建立基线，不推历史
        if last_id is None:
            data["last_dynamic"][uid] = dyns[0]["id"]
            data["dynamic_bootstrapped"].add(uid)
            continue

        # 收集比 last_id 更新的动态（列表按新到旧）
        fresh = []
        for d in dyns:
            if d["id"] == last_id:
                break
            fresh.append(d)
        if not fresh:
            continue
        data["last_dynamic"][uid] = dyns[0]["id"]

        # 旧到新推送，最多一次推 5 条防刷屏
        for d in reversed(fresh[:5]):
            body = d["text"] or "（无文字内容）"
            if len(body) > 200:
                body = body[:200] + "……"
            text = (
                f"📢 {sub['name']} 发布了新{d['type_name']}\n\n"
                f"{body}\n\n"
                f"🔗 {d['url']}"
            )
            msg = Message(text)
            seg = await _image_seg(d.get("pic"))
            if seg is not None:
                msg += seg
            await _push_to_groups(sub["dynamic_groups"], msg, fallback=Message(text))


timings.add_job(check_live, "interval", minutes=1, misfire_grace_time=30, coalesce=True)
timings.add_job(check_dynamic, "interval", minutes=3, misfire_grace_time=60, coalesce=True)

gc.collect()
