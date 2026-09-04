import random
import datetime

from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent
from utils import credit

from ..base import state
from ..base.constants import (
    hidden_stickers, SECRET_MESSAGES, new_account, TRANSFER_DAILY_MAX,
)
from ..base.matchers import qiandao, qiandaohelp, jrys
from ..base.helpers import (
    parse_session, ensure_registered,
    acquire_jrys, get_sticker, generate_new_sticker, acquire_sticker,
    unlock_segment, check_all_achiv, localpath_to_base64,
)


@qiandao.handle()
async def _(bot: Bot, ev: MessageEvent):
    res = '\n'
    user_id, group_id = parse_session(ev)

    once_reg = 0
    if user_id not in state.data:
        once_reg = 1
        state.data[user_id] = new_account()
        res += '欢迎来到Airi的收藏世界！\n☑️ 发送指令 签到帮助 查看所有功能哦！\n\n'

    state.data[user_id]['last_check_time'] = datetime.datetime.now().timestamp()
    if not state.data[user_id]['check_times_daily']:
        state.data[user_id]['checked_days'] += 1
        state.data[user_id]['check_times_daily'] += 1
        rand_sticker = 17
        while rand_sticker in hidden_stickers:
            rand_sticker = random.randint(1, 100)
        random_credit = 2000 if random.randint(1, 100) == 1 else random.randint(100, 200)
        await credit.credit(user_id, random_credit)
        random_like = 0
        nows = datetime.datetime.now()
        res += '🗓️ {}年{}月{}日 今日已签到！\n'.format(nows.year, nows.month, nows.day)
        res += '🖋️ 已连续签到{}天\n'.format(state.data[user_id]['checked_days'])
        if random_like:
            res += '获得{}个资料卡点赞\n'.format(random_like)
        msg = MessageSegment.text(res)

        if acquire_sticker(user_id, rand_sticker):
            get_repeat_credit = 0
            new_sticker = await generate_new_sticker(rand_sticker, user_id)
            msg += MessageSegment.text('📦 获得第{}号收藏品\n🎉是NEW，好耶！🎉\n'.format(rand_sticker)) \
                + MessageSegment.image(new_sticker)
        else:
            get_repeat_credit = 50
            await credit.credit(user_id, 50)
            stk = await get_sticker(rand_sticker, user_id)
            stk_b64 = await localpath_to_base64(stk)
            msg += MessageSegment.text('📦 获得第{}号收藏品\n♻️ 重复辣，转化为50积分\n'.format(rand_sticker)) \
                + MessageSegment.image(stk_b64)

        msg += MessageSegment.text(
            '✅ 获得 {} 积分\n📥 当前拥有 {} 积分'.format(random_credit + get_repeat_credit, await credit.get_balance(user_id))
        )

        random_jrys = random.choice(['💫 来看看今天的运势！', '🔥 我的回合，抽签！', '✨今日运势✨'])
        jrys_img = await acquire_jrys(user_id)
        stk_b64 = await localpath_to_base64(jrys_img)
        msg += MessageSegment.text(f'\n\n{random_jrys}\n') + MessageSegment.image(stk_b64)

        if await credit.get_balance(user_id) >= 2000 and acquire_sticker(user_id, 20):
            msg += await unlock_segment(
                user_id, 20,
                '\n\n⭐ 隐藏成就解锁！\n🎖️ 积分达到2000：解锁隐藏收藏品20！\n🎉是NEW，好耶！🎉\n',
            )
        if state.data[user_id]['checked_days'] >= 7 and acquire_sticker(user_id, 100):
            msg += await unlock_segment(
                user_id, 100,
                '\n\n⭐ 隐藏成就解锁！\n🎖️ 连续签到7天：解锁隐藏收藏品100！\n🎉是NEW，好耶！🎉\n',
            )
        if random.randint(1, 100) == 1:
            msg += MessageSegment.text('\n\n' + random.choice(SECRET_MESSAGES))
    else:
        res += '❌ 重复签到{}次！\n'.format(state.data[user_id]['check_times_daily'])
        penalty = min(random.randint(10, 20), max(0, await credit.get_balance(user_id)))
        if penalty:
            await credit.debit(user_id, penalty)
        res += '⛔ 已扣除 {} 积分\n📥 当前拥有 {} 积分'.format(penalty, await credit.get_balance(user_id))
        msg = MessageSegment.text(res)

        if state.data[user_id]['check_times_daily'] == 1 and acquire_sticker(user_id, 13):
            msg += await unlock_segment(
                user_id, 13,
                '\n\n⭐ 隐藏成就解锁！\n🎖️ 重复签到1次：解锁隐藏收藏品13！\n🎉是NEW，好耶！🎉\n',
            )
        elif state.data[user_id]['check_times_daily'] == 5 and acquire_sticker(user_id, 37):
            msg += await unlock_segment(
                user_id, 37,
                '\n\n⭐ 隐藏成就解锁！\n🎖️ 重复签到5次：解锁隐藏收藏品37！\n🎉是NEW，好耶！🎉\n',
            )
        state.data[user_id]['check_times_daily'] += 1
        if random.randint(1, 100) == 1:
            msg += MessageSegment.text('\n\n' + random.choice(SECRET_MESSAGES))

    await qiandao.send(msg, at_sender=True)
    await check_all_achiv(user_id, bot, ev)


@qiandaohelp.handle()
async def _(bot: Bot, ev: MessageEvent):
    def node(name, content):
        return {"type": "node", "data": {"name": name, "uin": bot.self_id, "content": content}}

    cmd_list = '☑️ 指令列表：\n\
 -签到：字面意思\n\
 -签到帮助：显示该信息\n\
 -收藏信息：查看当前账户信息\n\
 -查看收藏：查看当前收藏集章版\n\
 -查看收藏X（X为数字）：查看编号为X的收藏\n\
 -收藏抽卡：花费100积分抽取一次收藏\n\
 -收藏抽卡X（X为数字）：抽X次\n（重复收藏返还50积分）\n（十连保底出1new）\n\
 -收藏主题：显示所有收藏主题\n\
 -收藏主题xxx：指定当前帐号收藏主题为xxx\n\
 -今日运势：查看你的今日运势！\n\
 -今日挑战：完成游戏获取积分！\n\
 -购买提示：花费500积分购买随机一条有关隐藏收藏品的提示信息\n\n\
（*以下指令需要@机器人*）\n\
 -@Airi 转给@...X个积分（X为数字）：转账给你@的人\n不支持转至未注册账户的人，单日转出限额{}积分，手续费10%（向上取整）\n\
 -@Airi 重生：重开存档\n\n\
 （更多功能实装中）'.format(TRANSFER_DAILY_MAX)

    gameplay = '☑️ 游戏玩法：\n\
每天签到可以获得积分、资料卡点赞以及随机一个收藏品。\n\
收藏品共计100个，其中95个可以通过抽取获得，其余5个为隐藏收藏品，只有当满足一定条件才可获得。\n\
每集齐一次1-100收藏品即可获得一个创世收藏品。创世收藏品共有五个，重生后再次集齐即可获得第二个，依此类推。\n\
你真能完成全收藏嘛~杂鱼大叔❤'

    custom = '☑️ 收藏主题可以自行定制！\n\
如果你手上有超级多的表情包，且想要为社区做出自己的贡献，不妨将它们发给开发者！\n\
需要素材：100个普通表情包 + 5个创世表情包，一张背景图片。\n准备好后打成压缩包，发送至开发者邮箱saki@saki.ln.cn并备注即可！\n\
如果有更高级的定制需求（集章卡背板，1-100数字蒙版等），可以联系开发者要psd文件！\n你的名字将会出现在你提供的定制主题上。\n\
收藏信息背景也可以自行定制！\n\
将你需要的图片发送至上述邮箱并备注即可！\n\
（支持多张，生成图片时随机挑选）'

    msg = [
        node("Momoi Airi Collection", '⚜️ Momoi Airi Collection\n一款签到 + 收藏的娱乐插件'),
        node("指令列表", cmd_list),
        node("游戏玩法", gameplay),
        node("定制说明", custom),
        node("版权信息", 'Powered By AiriCore Dev.'),
    ]
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=msg)


@jrys.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, group_id = parse_session(ev)
    await ensure_registered(jrys, user_id)

    jrys_img = await acquire_jrys(user_id)
    stk_b64 = await localpath_to_base64(jrys_img)
    await jrys.finish(MessageSegment.text('\n✨今日运势✨\n') + MessageSegment.image(stk_b64), at_sender=True)
