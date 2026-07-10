import random
import traceback
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from ..base.matchers import turtle_soup_on, matcher
from ..base.constants import max_group_turtle_perday
from ..base import state
from ..base.helpers import get_ids, check_data_existance, generate_help_message, construct_turtle_soup, construct_turtle_soup_history, turtle_soup, bot_nick
from ..base.constants import max_player_query_trial, max_player_truth_trial, max_group_trial, min_turtle_minutes

@turtle_soup_on.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        src = str(ev.message)[3:].strip()
        res = ""
        if not len(src):
            msg = await generate_help_message(bot, max_player_query_trial, max_player_truth_trial, max_group_trial, min_turtle_minutes, max_group_turtle_perday)
            await bot.send_group_forward_msg(group_id=gruop_id, messages=msg)
            return
        else:
            if state.data['group'][gruop_id]['times'] >= max_group_turtle_perday:
                raise ValueError('❌ 本群今日海龟汤游玩次数已达上限')
            elif 'turtle' in state.data['group'][gruop_id]:
                raise ValueError('💬 本群有正在进行中的游戏\n发送 历史 查看汤面及问答记录')
            elif src == "随机":
                if len(state.data['group'][gruop_id]['has_played']) == len(turtle_soup):
                    state.data['group'][gruop_id]['has_played'] = []
                turtle_pool = [x for x in list(range(len(turtle_soup))) if x not in state.data['group'][gruop_id]['has_played']]
                src = random.choice(turtle_pool)
            else:
                try:
                    src = int(src)
                except:
                    raise ValueError('❓ 指令用法：海龟汤 随机 或者 海龟汤 编号')
            res += f"编号：{src}\n游戏已开始，祝你好运!\n\n"
            state.data['group'][gruop_id]['times'] += 1
            state.data['group'][gruop_id]['turtle'] = await construct_turtle_soup(src, user_id)
            res += f"【汤面】\n{turtle_soup[state.data['group'][gruop_id]['turtle']['soup_id']]['story']}"
            history_msg = await construct_turtle_soup_history(bot.self_id, bot_nick, res)
            state.data['group'][gruop_id]['turtle']['history'].append(history_msg)
            res += "\n\nTip：AI反应需要一定时间，提问后请耐心等待，请勿重复发送！"
            await matcher.send(res)
            return
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)
