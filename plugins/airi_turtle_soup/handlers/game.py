import random
import traceback
import copy

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from ..base.matchers import turtle_soup_on, matcher
from ..base.constants import max_group_turtle_perday
from ..base import state
from ..base.helpers import get_ids, check_data_existance, generate_help_message, construct_turtle_soup, construct_turtle_soup_history, turtle_soup, bot_nick, _persist
from ..base.constants import max_player_query_trial, max_player_truth_trial, max_group_trial, min_turtle_minutes
from ..base.numbering import soup_id_to_number, soup_number_to_id
from utils import credit


TURTLE_SOUP_START_COST = credit.TURTLE_SOUP_START_COST

@turtle_soup_on.handle()
async def _(bot: Bot, ev: MessageEvent):
    receipt = None
    gruop_id = None
    previous_group = None
    try:
        gruop_id, user_id = await get_ids(ev)
        if gruop_id is None:
            return
        await check_data_existance(gruop_id, user_id)
        previous_group = copy.deepcopy(state.data['group'][gruop_id])
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
                soup_id = random.choice(turtle_pool)
            else:
                try:
                    soup_number = int(src)
                except (TypeError, ValueError):
                    raise ValueError('❓ 指令用法：海龟汤 随机 或者 海龟汤 编号')
                soup_id = soup_number_to_id(soup_number, len(turtle_soup))
                if soup_id is None:
                    raise ValueError(f'❌ 编号超出范围，当前可用编号：1 - {len(turtle_soup)}')
            receipt = await credit.charge(user_id, TURTLE_SOUP_START_COST)
            res += f"编号：{soup_id_to_number(soup_id)}\n游戏已开始，祝你好运!\n\n"
            state.data['group'][gruop_id]['times'] += 1
            state.data['group'][gruop_id]['turtle'] = await construct_turtle_soup(soup_id, user_id)
            res += f"【汤面】\n{turtle_soup[state.data['group'][gruop_id]['turtle']['soup_id']]['story']}"
            history_msg = await construct_turtle_soup_history(bot.self_id, bot_nick, res)
            state.data['group'][gruop_id]['turtle']['history'].append(history_msg)
            res += "\n\nTip：AI反应需要一定时间，提问后请耐心等待，请勿重复发送！"
            await _persist(raise_on_error=True)
            await matcher.send(res)
            return
    except credit.ChargeRejected as err:
        if gruop_id is not None and previous_group is not None:
            state.data['group'][gruop_id] = previous_group
        await matcher.send(str(err), reply_message=True)
    except ValueError as err:
        await credit.refund(receipt)
        if gruop_id is not None and previous_group is not None:
            state.data['group'][gruop_id] = previous_group
        await matcher.send(str(err), reply_message=True)
    except Exception:
        await credit.refund(receipt)
        if gruop_id is not None and previous_group is not None:
            state.data['group'][gruop_id] = previous_group
            try:
                await _persist()
            except Exception:
                pass
        logger.error(f"海龟汤开局处理失败:\n{traceback.format_exc()}")
        await matcher.send('❌ 开局时出错了，已记录日志', reply_message=True)
