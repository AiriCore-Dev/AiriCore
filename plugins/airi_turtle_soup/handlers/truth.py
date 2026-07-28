import asyncio
import traceback

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from ..base.matchers import truth, matcher
from ..base.constants import max_player_truth_trial, max_group_trial
from ..base import state
from ..base.helpers import get_ids, check_data_existance, get_usernick, construct_turtle_soup_history, call_llm, turtle_soup_truth_prompt, turtle_soup, end_game, strip_cq, _persist

LLM_MAX_ATTEMPTS = 3
LLM_RETRY_DELAY = 2


@truth.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        gruop_id, user_id = await get_ids(ev)
        if gruop_id is None:
            return
        await check_data_existance(gruop_id, user_id)
        if 'turtle' not in state.data['group'][gruop_id]:
            return
        src = strip_cq(str(ev.message)[3:])[:300]
        if len(src):
            if state.data['group'][gruop_id]['turtle']['players'][user_id]['truth_trial'] >= max_player_truth_trial:
                raise ValueError("❌ 你的猜汤底机会已用完")
            user_nick = await get_usernick(bot, gruop_id, user_id)
            is_tg = 0
            history_text = f"猜汤底：{src}"
            soup = turtle_soup[state.data['group'][gruop_id]['turtle']['soup_id']]
            llm_answer = None
            for attempt in range(LLM_MAX_ATTEMPTS):
                try:
                    llm_answer = await call_llm(
                        turtle_soup_truth_prompt.format(
                            soup['truth'], '\n'.join(soup['tips'])
                        ),
                        src, 0,
                    )
                except Exception as err:
                    text = str(err)
                    if 'Moderation Block' in text:
                        await matcher.send('语言因被AI检测到违反公序良俗而被拦截，请修改措辞后重新发送\n（猜汤底次数已返还）', reply_message=True)
                        return
                    logger.warning(f"海龟汤猜汤底 LLM 调用失败（第 {attempt + 1}/{LLM_MAX_ATTEMPTS} 次）: {err}")
                    if attempt + 1 >= LLM_MAX_ATTEMPTS:
                        await matcher.send('AI繁忙，请过一分钟后再试\n（猜汤底次数已返还）', reply_message=True)
                        return
                    await asyncio.sleep(LLM_RETRY_DELAY)
                else:
                    if llm_answer and llm_answer.startswith('猜测成功'):
                        is_tg = 1
                    break
            if not llm_answer:
                await matcher.send('AI没有给出有效回复，请稍后再试\n（猜汤底次数已返还）', reply_message=True)
                return
            await matcher.send(llm_answer, reply_message=True)
            history_text += f'\n\n答：{llm_answer}'
            history_msg = await construct_turtle_soup_history(user_id, user_nick, history_text)
            state.data['group'][gruop_id]['turtle']['history'].append(history_msg)
            state.data['group'][gruop_id]['turtle']['trial'] += 1
            state.data['group'][gruop_id]['turtle']['players'][user_id]['truth_trial'] += 1
            await _persist()
            if is_tg:
                await end_game("victory", gruop_id, bot, user_id, user_nick, max_group_trial, matcher)
            elif state.data['group'][gruop_id]['turtle']['trial'] >= max_group_trial:
                await end_game("trial_off", gruop_id, bot, user_id, user_nick, max_group_trial, matcher)
            return
        else:
            raise ValueError("❌ 请输入猜汤底内容")
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception:
        logger.error(f"海龟汤猜汤底处理失败:\n{traceback.format_exc()}")
        await matcher.send('❌ 处理猜汤底时出错了，已记录日志', reply_message=True)
