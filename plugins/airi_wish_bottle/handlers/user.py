import time
import random

from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from nonebot import logger

from ..base import state
from ..base.matchers import rxyp, jxyp, plxyp, wdxyp, xgxyp, zyxyp, xhxyp, jbxyp
from ..base.helpers import (
    parse_session, check_weijinci, generate_unique_id, add_bottle, delete_bottle,
    send_email, strip_cq,
)
import re

DAILY_COMMENT_LIMIT = 10


async def _notify_admin(bot: Bot, text: str) -> None:
    if not state.notification_account:
        logger.warning(f"未配置 notification_account，人工审核通知未发出: {text[:40]}")
        return
    try:
        await bot.send_private_msg(user_id=int(state.notification_account), message=text)
    except Exception as e:
        logger.warning(f"审核通知发送失败: {e}")


@rxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    if user_id is None:
        await rxyp.finish('💫 心愿瓶只能在群聊里使用哦', reply_message=True)
    raw = str(ev.message).strip()
    if raw == "扔心愿瓶":
        await rxyp.finish('💫 指令用法：扔心愿瓶 内容', reply_message=True)
    src = [0, strip_cq(raw[4:])]
    if not src[1]:
        await rxyp.finish('💫 指令用法：扔心愿瓶 内容', reply_message=True)
    if len(src[1]) > 500:
        await rxyp.finish(f'❌ 心愿长度超出500字限制，请重新填写！当前字数：{len(src[1])}', reply_message=True)
    iswj = await check_weijinci(src[1])
    if iswj:
        unique_id = await generate_unique_id(src[1])
        state.data['pending_bottles'][unique_id] = {"owner": user_nick, "owner_id": user_id, "content": src[1], "comments": [], "times": 0}
        await _notify_admin(bot, f'心愿瓶审核：{unique_id}\n{src[1]}')
        await rxyp.finish('❌ 未通过机器审核，请等待人工审核。人工审核结果将会以邮件形式告知。', reply_message=True)
    else:
        unique_id = await generate_unique_id(src[1])
        add_bottle(unique_id, user_nick, user_id, src[1], [], 0)
        await rxyp.finish(f'✅ 您的心愿瓶编号：{unique_id}，等待有缘人的开启......', reply_message=True)


@jxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    if user_id is None:
        await jxyp.finish('💫 心愿瓶只能在群聊里使用哦', reply_message=True)
    src = str(ev.message).split(' ', 1)
    if len(src) == 1:
        if src[0] == "捡心愿瓶":
            pool = list(state.data.get("bottles", {}).keys())
            if not pool:
                await jxyp.finish('❌ 现在还没有任何心愿瓶，先扔一个吧！', reply_message=True)
            unique_id = random.choice(pool)
        else:
            unique_id = src[0][4:].strip()
    else:
        unique_id = src[1].strip()
    if len(unique_id) != 8:
        await jxyp.finish(f'❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data["bottles"].keys():
        await jxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    msg = []
    res = f'💫 {user_nick}拾取的心愿瓶'
    msg.append({"type": "node", "data": {"name": "Momoi Airi Wish Bottle", "uin": bot.self_id, "content": res}})
    res = state.data["bottles"][unique_id]["content"]
    msg.append({"type": "node", "data": {"name": "心愿瓶内容", "uin": bot.self_id, "content": res}})
    res = f'{unique_id}'
    msg.append({"type": "node", "data": {"name": "心愿瓶编号", "uin": bot.self_id, "content": res}})
    state.data["bottles"][unique_id]["times"] += 1
    res = f'心愿瓶持有者：{state.data["bottles"][unique_id]["owner"]}\n被拾取次数：{state.data["bottles"][unique_id]["times"]}'
    msg.append({"type": "node", "data": {"name": "心愿瓶基本信息", "uin": bot.self_id, "content": res}})
    res = "暂无评论" if not len(state.data["bottles"][unique_id]["comments"]) else '//: '.join(state.data["bottles"][unique_id]["comments"][::-1])
    msg.append({"type": "node", "data": {"name": "心愿瓶评论", "uin": bot.self_id, "content": res}})
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=msg)


@plxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    if user_id is None:
        await plxyp.finish('💫 心愿瓶只能在群聊里使用哦', reply_message=True)
    src = str(ev.message).split()
    if len(src) <= 2:
        await jxyp.finish('💫 指令用法：评论心愿瓶 编号 评论内容', reply_message=True)
    else:
        unique_id = src[1].strip()
    if len(unique_id) != 8:
        await jxyp.finish(f'❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data["bottles"].keys():
        await jxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    daily = state.data.setdefault("comments_daily", {})
    daily.setdefault(user_id, 0)
    if daily[user_id] >= DAILY_COMMENT_LIMIT:
        await plxyp.finish(
            f'❌ 该账号今日可评论次数已达上限（{DAILY_COMMENT_LIMIT} 次）', reply_message=True
        )
    comment = strip_cq(" ".join(src[2:]))
    if not comment:
        await plxyp.finish('💫 指令用法：评论心愿瓶 编号 评论内容', reply_message=True)
    if len(comment) > 20:
        await plxyp.finish(f'❌ 评论长度超出20字限制，请重新填写！当前字数：{len(comment)}', reply_message=True)
    daily[user_id] += 1
    iswj = await check_weijinci(comment)
    if iswj:
        uqid = await generate_unique_id(comment)
        comment_unique_id = str(time.time()) + '_' + uqid
        state.data['pending_comment'][comment_unique_id] = {"comment_to": unique_id, "from": user_nick + '_' + user_id, "content": comment}
        await _notify_admin(bot, f'评论审核：{unique_id}\n{comment}')
        await plxyp.finish('❌ 未通过机器审核，请等待人工审核。人工审核结果将会以邮件形式告知。', reply_message=True)
    else:
        state.data['bottles'][unique_id]['comments'].append(comment)
        if len(state.data['bottles'][unique_id]['comments']) > 30:
            state.data['bottles'][unique_id]['comments'].pop(0)
        await plxyp.finish(f'✅ 已评论编号为{unique_id}的心愿瓶：{comment}', reply_message=True)


@wdxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    if user_id is None:
        await wdxyp.finish('💫 心愿瓶只能在群聊里使用哦', reply_message=True)
    owned = state.data.setdefault('collections', {}).setdefault(user_id, [])
    msg = []
    res = f'💫 昵称：{user_nick}\nQQ号：{user_id}\n你总共有{len(owned)}个心愿瓶'
    msg.append({"type": "node", "data": {"name": "Momoi Airi Wish Bottle", "uin": bot.self_id, "content": res}})
    res = ''
    for unique_id in list(owned):
        bottle = state.data.get("bottles", {}).get(unique_id)
        if bottle is None:
            continue
        res += f'心愿瓶编号：{unique_id}\n内容摘要：{bottle["content"][:8]}\n\n'
    if len(res): msg.append({"type": "node", "data": {"name": "我的心愿瓶", "uin": bot.self_id, "content": res.strip()}})
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=msg)


@xgxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    if user_id is None:
        await xgxyp.finish('💫 心愿瓶只能在群聊里使用哦', reply_message=True)
    src = str(ev.message).split()
    if len(src) <= 2:
        await xgxyp.finish('💫 指令用法：修改心愿瓶 编号 内容', reply_message=True)
    unique_id = src[1].strip()
    if len(unique_id) != 8:
        await xgxyp.finish('❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data.get("bottles", {}):
        await xgxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    if str(state.data["bottles"][unique_id]["owner_id"]) != str(user_id):
        await xgxyp.finish('❌ 你不是该心愿瓶的拥有者！', reply_message=True)
    comment = strip_cq(" ".join(src[2:]))
    if not comment:
        await xgxyp.finish('💫 指令用法：修改心愿瓶 编号 内容', reply_message=True)
    if len(comment) > 500:
        await xgxyp.finish(f'❌ 心愿长度超出500字限制，请重新填写！当前字数：{len(comment)}', reply_message=True)
    iswj = await check_weijinci(comment)
    if iswj:
        state.data['pending_bottles'][unique_id] = {"owner": user_nick, "owner_id": user_id, "content": comment, "comments": state.data["bottles"][unique_id]["comments"], "times": state.data["bottles"][unique_id]["times"]}
        await _notify_admin(bot, f'心愿瓶修改审核：{unique_id}\n{comment}')
        await xgxyp.finish('❌ 未通过机器审核，请等待人工审核。人工审核结果将会以邮件形式告知。', reply_message=True)
    else:
        state.data['bottles'][unique_id]['owner'] = user_nick
        state.data['bottles'][unique_id]['content'] = comment
        await xgxyp.finish('修改成功', reply_message=True)


@zyxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    if user_id is None:
        await zyxyp.finish('💫 心愿瓶只能在群聊里使用哦', reply_message=True)
    src = str(ev.message).split()
    if len(src) != 3:
        await zyxyp.finish('💫 指令用法：转移心愿瓶 编号 @...', reply_message=True)
    unique_id = src[1].strip()
    if len(unique_id) != 8:
        await zyxyp.finish('❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data.get("bottles", {}):
        await zyxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    if str(state.data["bottles"][unique_id]["owner_id"]) != str(user_id):
        await zyxyp.finish('❌ 你不是该心愿瓶的拥有者！', reply_message=True)

    m = re.search(r'\[CQ:at,qq=(\d+)', src[2].strip())
    if m is None:
        await zyxyp.finish('💫 指令用法：转移心愿瓶 编号 @...', reply_message=True)
    transfer_id = m.group(1)
    if transfer_id == str(user_id):
        await zyxyp.finish('❌ 不能转给自己', reply_message=True)
    try:
        info = await bot.get_group_member_info(group_id=gruop_id, user_id=transfer_id)
        transfer_nick = info.get("card") or info.get("nickname") or transfer_id
    except Exception:
        transfer_nick = transfer_id
    try:
        add_bottle(unique_id, transfer_nick, transfer_id)
    except Exception as e:
        logger.warning(f"心愿瓶转移失败 {unique_id} -> {transfer_id}: {e}")
        await zyxyp.finish('❌ 转移失败，请稍后再试......', reply_message=True)
    await zyxyp.finish(f'✅ 操作成功！您已将编号为{unique_id}的心愿瓶转交给{transfer_nick}', reply_message=True)


@xhxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    if user_id is None:
        await xhxyp.finish('💫 心愿瓶只能在群聊里使用哦', reply_message=True)
    src = str(ev.message).split()
    if len(src) != 2:
        await xhxyp.finish('💫 指令用法：销毁心愿瓶 编号', reply_message=True)
    unique_id = src[1].strip()
    if len(unique_id) != 8:
        await xhxyp.finish('❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data.get("bottles", {}):
        await xhxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    if str(state.data["bottles"][unique_id]["owner_id"]) != str(user_id):
        await xhxyp.finish('❌ 你不是该心愿瓶的拥有者！', reply_message=True)
    delete_bottle(unique_id)
    await xhxyp.finish(f'🗑️ 编号为{unique_id}的心愿瓶已销毁', reply_message=True)


@jbxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    if user_id is None:
        await jbxyp.finish('💫 心愿瓶只能在群聊里使用哦', reply_message=True)
    src = str(ev.message).split()
    if len(src) <= 2:
        await jbxyp.finish('💫 指令用法：举报心愿瓶 编号 举报理由', reply_message=True)
    unique_id = src[1].strip()
    if len(unique_id) != 8:
        await jbxyp.finish('❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data.get("bottles", {}):
        await jbxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    comment = strip_cq(" ".join(src[2:]))[:200]
    jb_unique_id = str(time.time()) + '_' + unique_id
    state.data.setdefault('pending_jb', {})[jb_unique_id] = {
        'jbr': f'{user_nick}_{user_id}', 'unique_id': unique_id, 'comment': comment,
    }
    await _notify_admin(bot, f'举报审核：{jb_unique_id}')
    await jbxyp.finish('💬 您的举报已收到，请等待核实......', reply_message=True)
