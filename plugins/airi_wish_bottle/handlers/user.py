import gc
import time
import random

from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from ..base import state
from ..base.matchers import rxyp, jxyp, plxyp, wdxyp, xgxyp, zyxyp, xhxyp, jbxyp
from ..base.helpers import parse_session, check_weijinci, generate_unique_id, add_bottle, delete_bottle, send_email
import re


@rxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    src = str(ev.message).strip()
    if src == "扔心愿瓶":
        await rxyp.finish('💫 指令用法：扔心愿瓶 内容', reply_message=True)
    src = [0, src[4:].strip()]
    if len(src[1]) > 500:
        await rxyp.finish(f'❌ 心愿长度超出500字限制，请重新填写！当前字数：{len(src[1])}', reply_message=True)
    iswj = await check_weijinci(src[1])
    if iswj:
        unique_id = await generate_unique_id(src[1])
        state.data['pending_bottles'][unique_id] = {"owner": user_nick, "owner_id": user_id, "content": src[1], "comments": [], "times": 0}
        try:
            await bot.send_private_msg(user_id=int(state.notification_account), message=f'📛 心愿瓶审核：{unique_id}\n{src[1]}')
        except:
            pass
        await rxyp.finish('❌ 未通过机器审核，请等待人工审核。人工审核结果将会以邮件形式告知。', reply_message=True)
    else:
        unique_id = await generate_unique_id(src[1])
        add_bottle(unique_id, user_nick, user_id, src[1], [], 0)
        await rxyp.finish(f'✅ 您的心愿瓶编号：{unique_id}，等待有缘人的开启......', reply_message=True)


@jxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    src = str(ev.message).split(' ', 1)
    if len(src) == 1:
        if src[0] == "捡心愿瓶":
            unique_id = random.choice(list(state.data["bottles"].keys()))
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
    del msg, res
    gc.collect()


@plxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    src = str(ev.message).split()
    if len(src) <= 2:
        await jxyp.finish('💫 指令用法：评论心愿瓶 编号 评论内容', reply_message=True)
    else:
        unique_id = src[1].strip()
    if len(unique_id) != 8:
        await jxyp.finish(f'❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data["bottles"].keys():
        await jxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    try:
        state.data["comments_daily"][user_id]
    except:
        state.data["comments_daily"][user_id] = 0
    if state.data["comments_daily"][user_id] > 10:
        await jxyp.finish(f'❌ 该账号今日可评论次数已达上限', reply_message=True)
    comment = " ".join(src[2:])
    if len(comment) > 20:
        await rxyp.finish(f'❌ 评论长度超出20字限制，请重新填写！当前字数：{len(comment)}', reply_message=True)
    state.data["comments_daily"][user_id] += 1
    iswj = await check_weijinci(comment)
    if iswj:
        uqid = await generate_unique_id(comment)
        comment_unique_id = str(time.time()) + '_' + uqid
        state.data['pending_comment'][comment_unique_id] = {"comment_to": unique_id, "from": user_nick + '_' + user_id, "content": comment}
        try:
            await bot.send_private_msg(user_id=int(state.notification_account), message=f'📛 评论审核：{unique_id}\n{comment}')
        except:
            pass
        await rxyp.finish('❌ 未通过机器审核，请等待人工审核。人工审核结果将会以邮件形式告知。', reply_message=True)
    else:
        state.data['bottles'][unique_id]['comments'].append(comment)
        if len(state.data['bottles'][unique_id]['comments']) > 30:
            state.data['bottles'][unique_id]['comments'].pop(0)
        await rxyp.finish(f'✅ 已评论编号为{unique_id}的心愿瓶：{comment}', reply_message=True)


@wdxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    try:
        state.data['collections'][user_id]
    except:
        state.data['collections'][user_id] = []
    msg = []
    res = f'💫 昵称：{user_nick}\nQQ号：{user_id}\n你总共有{len(state.data["collections"][user_id])}个心愿瓶'
    msg.append({"type": "node", "data": {"name": "Momoi Airi Wish Bottle", "uin": bot.self_id, "content": res}})
    res = ''
    for unique_id in state.data['collections'][user_id]:
        res += f'心愿瓶编号：{unique_id}\n内容摘要：{state.data["bottles"][unique_id]["content"][:8]}\n\n'
    if len(res): msg.append({"type": "node", "data": {"name": "我的心愿瓶", "uin": bot.self_id, "content": res.strip()}})
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=msg)
    del msg, res
    gc.collect()


@xgxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    src = str(ev.message).split()
    if len(src) <= 2:
        await jxyp.finish('💫 指令用法：修改心愿瓶 编号 内容', reply_message=True)
    else:
        unique_id = src[1].strip()
    if len(unique_id) != 8:
        await jxyp.finish(f'❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data["bottles"].keys():
        await jxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    if state.data["bottles"][unique_id]["owner_id"] != user_id:
        await jxyp.finish(f'❌ 你不是该心愿瓶的拥有者！', reply_message=True)
    comment = str(ev.message)
    comment = comment[comment.find(unique_id) + 8:].strip()
    iswj = await check_weijinci(comment)
    if iswj:
        state.data['pending_bottles'][unique_id] = {"owner": user_nick, "owner_id": user_id, "content": comment, "comments": state.data["bottles"][unique_id]["comments"], "times": state.data["bottles"][unique_id]["times"]}
        await rxyp.finish('❌ 未通过机器审核，请等待人工审核。人工审核结果将会以邮件形式告知。', reply_message=True)
    else:
        state.data['bottles'][unique_id]['owner'] = user_nick
        state.data['bottles'][unique_id]['content'] = comment
        await rxyp.finish(f'修改成功', reply_message=True)


@zyxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    src = str(ev.message).split()
    if len(src) != 3:
        await jxyp.finish('💫 指令用法：转移心愿瓶 编号 @...', reply_message=True)
    else:
        unique_id = src[1].strip()
    if len(unique_id) != 8:
        await jxyp.finish(f'❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data["bottles"].keys():
        await jxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    if state.data["bottles"][unique_id]["owner_id"] != user_id:
        await jxyp.finish(f'❌ 你不是该心愿瓶的拥有者！', reply_message=True)
    try:
        cq_code = re.findall(r'\[CQ:at,qq=\d+.*\]', src[2].strip())[0]
        transfer_id = re.findall('\d+', cq_code)[0]
        transfer_nick = await bot.get_group_member_info(group_id=gruop_id, user_id=transfer_id)
        transfer_nick = (transfer_nick.get("nickname") or transfer_nick.get("card") or transfer_id)
        add_bottle(unique_id, transfer_nick, transfer_id)
    except:
        await jxyp.finish('❌ 系统繁忙，请稍后再试......', reply_message=True)
    else:
        await jxyp.finish(f'✅ 操作成功！您已将编号为{unique_id}的心愿瓶转交给{transfer_nick}', reply_message=True)


@xhxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    src = str(ev.message).split()
    if len(src) != 2:
        await jxyp.finish('💫 指令用法：销毁心愿瓶 编号', reply_message=True)
    else:
        unique_id = src[1].strip()
    if len(unique_id) != 8:
        await jxyp.finish(f'❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data["bottles"].keys():
        await jxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    if state.data["bottles"][unique_id]["owner_id"] != user_id:
        await jxyp.finish(f'❌ 你不是该心愿瓶的拥有者！', reply_message=True)
    delete_bottle(unique_id)
    await jxyp.finish(f'🗑️ 编号为{unique_id}的心愿瓶已销毁', reply_message=True)


@jbxyp.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, gruop_id, user_nick = await parse_session(bot, ev)
    src = str(ev.message).split()
    if len(src) <= 2:
        await jxyp.finish('💫 指令用法：举报心愿瓶 编号 举报理由', reply_message=True)
    else:
        unique_id = src[1].strip()
    if len(unique_id) != 8:
        await jxyp.finish(f'❌ 请检查心愿瓶编号格式！', reply_message=True)
    elif unique_id not in state.data["bottles"].keys():
        await jxyp.finish(f'❌ 编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    comment = " ".join(src[2:])
    jb_unique_id = str(time.time()) + '_' + unique_id
    state.data['pending_jb'][jb_unique_id] = {'jbr': f'{user_nick}_{user_id}', 'unique_id': unique_id, 'comment': comment}
    try:
        await bot.send_private_msg(user_id=int(state.notification_account), message=f'📛 举报审核：{jb_unique_id}')
    except:
        pass
    await jxyp.finish(f'💬 您的举报已收到，请等待核实......', reply_message=True)
