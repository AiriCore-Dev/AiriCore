import hmac
import hashlib
import datetime

from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent

from ..base import state
from ..base.constants import DIFFICULTY, CREDIT_BY_DIFF, asset
from ..base.matchers import daily_challenge, flag_submit
from ..base.helpers import (
    parse_session, ensure_registered,
    acquire_sticker, unlock_segment, localpath_to_base64,
)


@daily_challenge.handle()
async def _(bot: Bot, ev: MessageEvent):
    nows = datetime.datetime.now()
    res = MessageSegment.text('㊙️ 快来挑战今日份数独题目吧！\n{}年{}月{}日\n'.format(nows.year, nows.month, nows.day))
    for i in range(1, 4):
        stk = asset('utils', 'sudoku', f'sdk_diff_{i}.jpg')
        stk_b64 = await localpath_to_base64(stk)
        res += MessageSegment.text(f'\n{DIFFICULTY[i]}难度 - {CREDIT_BY_DIFF[i]}积分')
        res += MessageSegment.image(stk_b64)
    res += MessageSegment.text('\n\n📬 如何提交：\n请访问 https://www.airi.asia/posts/mac_flag_generator/ 并按照网页指示进行操作。')
    await daily_challenge.finish(res, reply_message=True)


@flag_submit.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, group_id = parse_session(ev)
    src = str(ev.message).strip()[5:-1]
    await ensure_registered(flag_submit, user_id)

    if not any(str(state.game_ans[i] or '').strip() for i in range(1, 4)):
        await flag_submit.finish('⛔ 今日挑战还未生成，请稍后再试', reply_message=True)

    for i in range(1, 4):
        answer = str(state.game_ans[i] or '').strip()
        if not answer:
            continue
        hash_res = hmac.new(user_id.encode(), answer.encode(), hashlib.md5).hexdigest()
        if hmac.compare_digest(src, hash_res):
            if not state.data[user_id]['daily_challenge'][i]:
                state.data[user_id]['credits'] += CREDIT_BY_DIFF[i]
                state.data[user_id]['daily_challenge'][i] = 1
                msg = MessageSegment.text(
                    f'\n✅ 提交成功！\n恭喜你解出了每日挑战{DIFFICULTY[i]}难度，获得{CREDIT_BY_DIFF[i]}积分奖励！\n当前积分：{state.data[user_id]["credits"]}'
                )
                if state.data[user_id]['credits'] >= 2000 and acquire_sticker(user_id, 20):
                    msg += await unlock_segment(
                        user_id, 20,
                        '\n\n⭐ 隐藏成就解锁！\n🎖️ 积分达到2000：解锁隐藏收藏品20！\n🎉是NEW，好耶！🎉\n',
                    )
                await flag_submit.finish(msg, at_sender=True, reply_message=True)
            else:
                await flag_submit.finish(f'❌ 今日已完成{DIFFICULTY[i]}难度，请勿重复提交！', reply_message=True)
    await flag_submit.finish('⛔ 你提交的Flag好像不是很对哦', reply_message=True)
