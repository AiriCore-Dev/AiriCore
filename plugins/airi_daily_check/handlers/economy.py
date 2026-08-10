import re
import math
import random

from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent

from utils.onebot_query import member_name

from ..base import state
from ..base.constants import SECRET_MESSAGES, TRANSFER_DAILY_MAX
from ..base.matchers import transcation, reborn, buy_tip
from ..base.helpers import (
    parse_session, ensure_registered,
    generate_new_sticker, acquire_sticker, check_all_achiv,
)


@transcation.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(transcation, user_id)

    try:
        cq_code = re.findall(r'\[CQ:at,qq=\d+.*\]', src)[0]
        transfer_id = re.findall(r'\d+', cq_code)[0]
        transfer_num = re.findall(r'[-]?\d+[个]?积分', src)[0]
        transfer_num = transfer_num[:-2] if transfer_num[:-2].isdigit() else transfer_num[:-3]
        transfer_num = int(transfer_num)
        assert transfer_num > 0
    except:
        await transcation.finish(
            '❌ 指令格式不正确！\n用法：转账 @某人 xx积分（每天累计上限 {} 积分）'.format(
                TRANSFER_DAILY_MAX
            ),
            reply_message=True,
        )

    if transfer_id == user_id:
        await transcation.finish('❌ 不能给自己转账', reply_message=True)
    if transfer_id not in state.data:
        await transcation.finish('❌ 收款方未注册账号', reply_message=True)

    user_nick = await member_name(bot, group_id, transfer_id)
    taxs = math.ceil(transfer_num * 1.0 / 10)
    if transfer_num + taxs > state.data[user_id]['credits']:
        await transcation.finish('❌ 你的积分余额不足！\n现有积分：{}\n需要积分(含税)：{}'.format(state.data[user_id]['credits'], transfer_num + taxs), reply_message=True)
    sent_today = state.data[user_id]['receive_transfer_daily']
    if transfer_num + sent_today > TRANSFER_DAILY_MAX:
        await transcation.finish('❌ 已超出今日转出限额！\n账户转出限额：{}积分/天\n今日已转出：{}'.format(TRANSFER_DAILY_MAX, sent_today), reply_message=True)

    state.data[user_id]['receive_transfer_daily'] += transfer_num
    state.data[user_id]['credits'] -= transfer_num + taxs
    state.data[transfer_id]['credits'] += transfer_num
    await transcation.send('✅ 交易成功！\n你已向{}转出了{}积分\nAiri从中收取了{}点手续费(10%)\n剩余积分：{}'.format(user_nick, transfer_num, taxs, state.data[user_id]['credits']), reply_message=True)

    if state.data[transfer_id]['credits'] >= 2000 and acquire_sticker(transfer_id, 20):
        new_sticker = await generate_new_sticker(20, transfer_id)
        msg = MessageSegment.at(transfer_id) \
            + MessageSegment.text('\n⭐ 隐藏成就解锁！\n🎖️ 积分达到2000：解锁隐藏收藏品20！\n🎉是NEW，好耶！🎉\n') \
            + MessageSegment.image(new_sticker)
        await transcation.send(msg)


@reborn.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(reborn, user_id)

    if src == '重生':
        msg = '\n\
🕗 请仔细阅读以下说明：\n\
 ❌ 以下账户进度会被清空：\n\
  · 积分\n\
  · 1-100号收藏品\n\
 📥 以下账户进度*不会*被清空：\n\
  · 连续签到天数\n\
  · 今日签到情况\n\
  · 今日转账限额\n\
  · 创世收藏品（101-105）\n\
  · 重生次数计数器\n\
 ⚖️ 存在以下情况将无法进行重生操作：\n\
  · 积分 < 0\n\
（友情提醒：只有完成1-100全进度才能累加重生次数）\n\
❗该操作不可逆，请慎重操作❗\n\
🔔 请再次确认你的重生请求，如果确定重生，@我并键入如下内容:\n\
重生（空格）你的QQ号（空格）我已阅读重生说明，请帮我重置账户。\n\
⛔ 存在错字、漏字等情况将不会执行重生操作。'
        await reborn.finish(msg, at_sender=True, reply_message=True)
    elif src == '重生 {} 我已阅读重生说明，请帮我重置账户。'.format(user_id):
        if state.data[user_id]['credits'] < 0:
            await reborn.finish('😡 捡漏失败：积分<0还想重置账户？爬爬爬！', reply_message=True)
        await check_all_achiv(user_id, bot, ev)
        state.data[user_id]['credits'] = 0
        state.data[user_id]['collections'] = [i for i in range(101, 106) if i in state.data[user_id]['collections']]
        if state.data[user_id]['need_reborn']:
            state.data[user_id]['need_reborn'] = 0
            state.data[user_id]['reborn_times'] += 1
        await reborn.send('\n✅ 重生操作已成功完成！', at_sender=True, reply_message=True)
    else:
        await reborn.finish('\n❌ 请求不正确！请检查是否存在错字、漏字等情况。', at_sender=True, reply_message=True)


@buy_tip.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, group_id = parse_session(ev)
    await ensure_registered(buy_tip, user_id)

    if state.data[user_id]['credits'] < 500:
        await buy_tip.finish('😡 500积分都拿不出来的吗！', reply_message=True)
    else:
        state.data[user_id]['credits'] -= 500
        await buy_tip.finish(
            f'{random.choice(SECRET_MESSAGES)}\n\n剩余积分：{state.data[user_id]["credits"]}',
            reply_message=True,
        )
