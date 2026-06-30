import os
import json
import time
import random
import shutil
import pickle
import nonebot
import traceback
from utils.totp_2fa import totp_verify
from openai import AsyncOpenAI
from nonebot import get_driver, on_startswith, require
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent

timings = require("nonebot_plugin_apscheduler").scheduler
driver = get_driver()
#--------------------
data = {}
'''
data: 
    ['group']: 
        [{group_id}]: 
            ['times']: int
            ['has_played']: list
            ['turtle']: 
                ['soup_id']: int
                ['creator']: str
                ['create_time']: int
                ['trial']: int
                ['players']['user_id']: 
                    ['query_trial']: int
                    ['truth_trial']: int
                ['history']: list
    ['player']:
        [{user_id}]:
            ...
'''

#-----CONFIG--------
bot_nick = "Momoi Airi"
max_group_turtle_perday = 5
max_player_query_trial = 15
max_player_truth_trial = 3
max_group_trial = 90
min_turtle_minutes = 30
difficulty = {
    "简单": [20, 10],
    "普通": [15, 7],
    "困难": [10, 5],
    "大师": [5, 3]
}
_2fa_key = getattr(driver.config, "_2fa_key", "")

#--------------------

matcher = on_startswith('通用matcher')
superuser_debug = on_startswith('tdebug ',priority=5,block=True,rule=to_me(),permission=SUPERUSER)
turtle_soup_on = on_startswith('海龟汤',priority=5,block=True)
query = on_startswith('提问',priority=5,block=True)
truth = on_startswith('猜汤底',priority=5,block=True)
history = on_startswith('历史',priority=5,block=True)
times_used = on_startswith('次数',priority=5,block=True)
force_end = on_startswith('结束海龟汤',priority=5,block=True)

#--------------------

@driver.on_startup
async def load_json():
    global data
    try:
        with open(os.path.join('data', 'airi_turtle_soup', 'data.pk'),'rb') as f:
            data = pickle.load(f)
    except:
        os.makedirs(os.path.join('data', 'airi_turtle_soup'))
        await save_to_json()

@driver.on_shutdown
async def save_to_json():
    global data
    with open(os.path.join('data', 'airi_turtle_soup', 'data.pk'),'wb') as f:
        pickle.dump(data, f)
 
async def daily_clear():
    global data
    for i in data['group']:
        data['group'][i]['times'] = 0
    await save_to_json()

async def save_data_backup():
    await save_to_json()
    shutil.copyfile(os.path.join('data', 'airi_turtle_soup', 'data.pk'),os.path.join('data', 'airi_turtle_soup', 'data.pk.bak'))

timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)  
  
#--------------------

with open(os.path.join(os.path.dirname(__file__), 'utils', 'generate_turtle_soup_prompt.txt'),'r',encoding='utf-8') as f:
    generate_turtle_soup_prompt = f.read()    
with open(os.path.join(os.path.dirname(__file__), 'utils', 'turtle_soup_question_prompt.txt'),'r',encoding='utf-8') as f:
    turtle_soup_question_prompt = f.read()    
with open(os.path.join(os.path.dirname(__file__), 'utils', 'turtle_soup_truth_prompt.txt'),'r',encoding='utf-8') as f:
    turtle_soup_truth_prompt = f.read()
with open(os.path.join(os.path.dirname(__file__), 'utils', 'turtle_soup.json'),'r',encoding='utf-8') as f:
    turtle_soup = json.load(f)
    
#--------------------
    
client = AsyncOpenAI(
    api_key = getattr(driver.config, "llm_api_key", ""),
    base_url = getattr(driver.config, "llm_base_url", "")
)

async def call_llm(prompt, input, deepseek):
    completion = await client.chat.completions.create(
        model = getattr(driver.config, "other_llm_model", ""),
        messages=[
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": input
            }
        ],
        max_completion_tokens=10,
        temperature=0.1,
        top_p=0.1,
        stream=False,
        stop=None,
        frequency_penalty=0,
        presence_penalty=0.1,
        extra_body={
            "thinking": {"type": "enabled" if deepseek else "disabled"}
        }
    )
    return json.loads(completion.model_dump_json())["choices"][0]["message"]["content"]

async def check_data_existance(gruop_id, user_id):
    global data
    try:
        data['group']
    except:
        data['group'] = {}
    try:
        data['player']
    except:
        data['player'] = {}
    try:
        data['group'][gruop_id]
    except:
        data['group'][gruop_id] = {"times": 0, "has_played": []}
    try:
        data['player'][user_id]
    except:
        data['player'][user_id] = {"rank": 0}
    if 'turtle' in data['group'][gruop_id]:
        try:
            data['group'][gruop_id]['turtle']['players'][user_id]
        except:
            data['group'][gruop_id]['turtle']['players'][user_id] = {'query_trial': 0, 'truth_trial': 0}

async def construct_turtle_soup(soup_id, creator):
    res = {}
    res['soup_id'] = soup_id
    res['creator'] = creator
    res['create_time'] = int(time.time())
    res['trial'] = 0
    res['players'] = {}
    res['history'] = []
    return res
    
async def construct_turtle_soup_history(user_id, user_nick, content):
    return {"type": "node", "data": {"name": user_nick, "uin": user_id, "content": content}}
    
async def get_usernick(bot, gruop_id, user_id):
    user_nick = await bot.get_group_member_info(group_id=gruop_id, user_id=user_id)
    user_nick = (user_nick.get("nickname") or user_nick.get("card") or user_id)
    return user_nick

async def get_ids(ev):
    session_id = str(ev.get_session_id())
    if 'group' in session_id:
        split_id = session_id.split("_")
        user_id = split_id[2]
        gruop_id = split_id[1]
    else:
        user_id = session_id
        gruop_id = None
    return gruop_id, user_id    
    
async def generate_help_message(bot):
    msg = []  
    res = '\
🐢 Momoi Airi Turtle Soup\n\
你已经猜到结局了吗？\n\
一个人也能玩的海龟汤推理故事\n\
海龟汤中虽然会告诉你故事结局，\n但也许会好奇“为什么会这样啊？”……'
    msg.append({"type": "node", "data": {"name": "Momoi Airi Turtle Soup", "uin": bot.self_id, "content": res}})

    res = '\
📒 指令列表：\n\
  -海龟汤：显示此帮助信息\n\
  -海龟汤 随机：随机开启一篇海龟汤游戏\n\
  -海龟汤 X：开启编号为X的海龟汤游戏\n\
  -提问 xxx：进行提问\n\
  -猜汤底 xxx：判断真相\n\
  -次数：查看自己和群已用次数\n\
  -历史：查看历史记录\n\
  -结束海龟汤：提前结束游戏\n\
*注意：参数之间请使用空格隔开！\n\
正确示范：提问 xxx\n\
错误示范：提问xxx'
    msg.append({"type": "node", "data": {"name": "指令列表", "uin": bot.self_id, "content": res}})
    
    res = '\
☑️ 游戏玩法：\n\
海龟汤是一款趣味情境推理游戏，出题人先给出一段简短悬疑的故事结局（汤面），玩家通过提出封闭式问题推进推理，出题人仅以“是”“否”作答，玩家需根据回答拼凑线索，最终还原整个故事的完整脉络（汤底）。'
    msg.append({"type": "node", "data": {"name": "游戏玩法", "uin": bot.self_id, "content": res}})
    
    res = '\
对于每场游戏：\n\
  ◆一人仅限进行{}次询问，{}次猜汤底\n\
  ◆如果一人无法完成游戏，call上其他小伙伴一起来吧\n\
  ◆所有群成员的询问/猜汤底次数合计上限为{}次，超过次数会强制结束游戏。\n\
  ◆游戏开始{}分钟后才可提前结束游戏\n\n\
对于每个群：\n\
  ◆每个群单日最多可进行{}场游戏'.format(max_player_query_trial, max_player_truth_trial, max_group_trial, min_turtle_minutes, max_group_turtle_perday)
    msg.append({"type": "node", "data": {"name": "说明", "uin": bot.self_id, "content": res}})
    
    msg.append({"type": "node", "data": {"name": "版权信息", "uin": bot.self_id, "content": 'Powered By AiriCore Dev.'}})
    return msg

async def end_game(mode, gruop_id, bot, user_id, user_nick):
    global data
    if mode == "trial_off":
        msg = f'❌ 总轮询次数已超过{max_group_trial}次，游戏结束！\n太失败了，怎么这么久都没猜出来……'
    elif mode == "victory":
        msg = f"🧩 PURE MEMORY\n恭喜{user_nick}完成最后一块记忆拼图\n\n【汤底】\n{turtle_soup[data['group'][gruop_id]['turtle']['soup_id']]['truth']}"
        if data['group'][gruop_id]['turtle']['soup_id'] not in data['group'][gruop_id]['has_played']:
            data['group'][gruop_id]['has_played'].append(data['group'][gruop_id]['turtle']['soup_id'])
    elif mode == "break":
        msg = f'🚫 发起者终止了本次游戏'
    history_msg = await construct_turtle_soup_history(bot.self_id, bot_nick, msg)
    data['group'][gruop_id]['turtle']['history'].append(history_msg)
    await matcher.send(f'{msg}\n\n以下是历史记录：')
    await bot.send_group_forward_msg(group_id=gruop_id, messages=data['group'][gruop_id]['turtle']['history'])
    del data['group'][gruop_id]['turtle']

#-------------------------------------------

@turtle_soup_on.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        global data
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        src = str(ev.message)[3:].strip()
        res = ""
        if not len(src):
            msg = await generate_help_message(bot)     
            await bot.send_group_forward_msg(group_id=gruop_id, messages=msg)
            return
        else:
            if data['group'][gruop_id]['times'] >= max_group_turtle_perday:
                raise ValueError('❌ 本群今日海龟汤游玩次数已达上限')
            elif 'turtle' in data['group'][gruop_id]:
                raise ValueError('💬 本群有正在进行中的游戏\n发送 历史 查看汤面及问答记录')
            elif src == "随机":
                if len(data['group'][gruop_id]['has_played']) == len(turtle_soup):
                    data['group'][gruop_id]['has_played'] = []
                turtle_pool = [x for x in list(range(len(turtle_soup))) if x not in data['group'][gruop_id]['has_played']]
                src = random.choice(turtle_pool)
            else:
                try:
                    src = int(src)
                except:
                    raise ValueError('❓ 指令用法：海龟汤 随机 或者 海龟汤 编号')
            res += f"编号：{src}\n游戏已开始，祝你好运!\n\n"
            data['group'][gruop_id]['times'] += 1
            data['group'][gruop_id]['turtle'] = await construct_turtle_soup(src, user_id)
            res += f"【汤面】\n{turtle_soup[data['group'][gruop_id]['turtle']['soup_id']]['story']}"
            history_msg = await construct_turtle_soup_history(bot.self_id, bot_nick, res)
            data['group'][gruop_id]['turtle']['history'].append(history_msg)
            res += "\n\nTip：AI反应需要一定时间，提问后请耐心等待，请勿重复发送！"
            await matcher.send(res)
            return
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)
        
@query.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        global data
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        try:
            data['group'][gruop_id]['turtle']
        except:
            return
        src = str(ev.message)[2:].strip()
        if len(src):
            if data['group'][gruop_id]['turtle']['players'][user_id]['query_trial'] >= max_player_query_trial:
                raise ValueError("❌ 你的提问机会已用完")
            user_nick = await get_usernick(bot, gruop_id, user_id)
            history_text = f"提问：{src}"
            while 1:
                try:
                    llm_answer = await call_llm(turtle_soup_question_prompt.format(turtle_soup[data['group'][gruop_id]['turtle']['soup_id']]['story'], turtle_soup[data['group'][gruop_id]['turtle']['soup_id']]['truth'], '\n'.join(turtle_soup[data['group'][gruop_id]['turtle']['soup_id']]['tips'])), src, 0)
                except Exception as err:
                    if 'Moderation Block' in str(err):
                        await matcher.send('语言因被AI检测到违反公序良俗而被拦截，请修改措辞后重新发送\n（提问次数已返还）', reply_message=True)
                        return
                    await matcher.send('AI繁忙，请过一分钟后再试\n（提问次数已返还）', reply_message=True)
                    return
                else:
                    break
            await matcher.send(llm_answer, reply_message=True)
            history_text += f'\n\n答：{llm_answer}'
            history_msg = await construct_turtle_soup_history(user_id, user_nick, history_text)
            data['group'][gruop_id]['turtle']['history'].append(history_msg)
            data['group'][gruop_id]['turtle']['trial'] += 1
            data['group'][gruop_id]['turtle']['players'][user_id]['query_trial'] += 1
            if data['group'][gruop_id]['turtle']['trial'] >= max_group_trial:
                await end_game("trial_off", gruop_id, bot, user_id, user_nick)
            return
        else:
            raise ValueError("❌ 请输入提问内容")
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)
        
@truth.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        global data
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        try:
            data['group'][gruop_id]['turtle']
        except:
            return
        src = str(ev.message)[3:].strip()
        if len(src):
            if data['group'][gruop_id]['turtle']['players'][user_id]['truth_trial'] >= max_player_truth_trial:
                raise ValueError("❌ 你的猜汤底机会已用完")
            user_nick = await get_usernick(bot, gruop_id, user_id)
            is_tg = 0
            history_text = f"猜汤底：{src}"
            while 1:
                try:
                    llm_answer = await call_llm(turtle_soup_truth_prompt.format(turtle_soup[data['group'][gruop_id]['turtle']['soup_id']]['truth'], '\n'.join(turtle_soup[data['group'][gruop_id]['turtle']['soup_id']]['tips'])), src, 0)
                    if llm_answer.startswith('猜测成功'):
                        is_tg = 1
                except Exception as err:
                    if 'Moderation Block' in str(err):
                        await matcher.send('语言因被AI检测到违反公序良俗而被拦截，请修改措辞后重新发送\n（猜汤底次数已返还）', reply_message=True)
                        return
                    if 'request' in str(err):
                        await matcher.send('AI繁忙，请过一分钟后再试\n（猜汤底次数已返还）', reply_message=True)
                        return
                else:
                    break
            await matcher.send(llm_answer, reply_message=True)
            history_text += f'\n\n答：{llm_answer}'
            history_msg = await construct_turtle_soup_history(user_id, user_nick, history_text)
            data['group'][gruop_id]['turtle']['history'].append(history_msg)
            data['group'][gruop_id]['turtle']['trial'] += 1
            data['group'][gruop_id]['turtle']['players'][user_id]['truth_trial'] += 1
            if is_tg:
                await end_game("victory", gruop_id, bot, user_id, user_nick)
            elif data['group'][gruop_id]['turtle']['trial'] >= max_group_trial:
                await end_game("trial_off", gruop_id, bot, user_id, user_nick)
            return
        else:
            raise ValueError("❌ 请输入猜汤底内容")
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)

@history.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        global data
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        try:
            data['group'][gruop_id]['turtle']
        except:
            return
        await bot.send_group_forward_msg(group_id=gruop_id, messages=data['group'][gruop_id]['turtle']['history'])
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)
        
@times_used.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        global data
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        try:
            data['group'][gruop_id]['turtle']
        except:
            return
        res = f"本场游戏：\n  -本人已提问次数：{data['group'][gruop_id]['turtle']['players'][user_id]['query_trial']}/{max_player_query_trial}\n  -本人已猜汤底次数：{data['group'][gruop_id]['turtle']['players'][user_id]['truth_trial']}/{max_player_truth_trial}\n  -群总轮询次数：{data['group'][gruop_id]['turtle']['trial']}/{max_group_trial}\n\n本群：\n  -群今日已进行游戏场数：{data['group'][gruop_id]['times']}/{max_group_turtle_perday}"
        await matcher.send(res, reply_message=True)
        return
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)

@force_end.handle()
async def _(bot: Bot, ev: MessageEvent):
    try:
        global data
        gruop_id, user_id = await get_ids(ev)
        await check_data_existance(gruop_id, user_id)
        try:
            data['group'][gruop_id]['turtle']
        except:
            return
        user_nick = await get_usernick(bot, gruop_id, user_id)
        if user_id != data['group'][gruop_id]['turtle']['creator']:
            raise ValueError('❌ 你不是提问的发起者')
        time_passed = (int(time.time()) - data['group'][gruop_id]['turtle']['create_time']) // 60
        if time_passed < min_turtle_minutes:
            dmesg = random.choice([
                f"这才过了{time_passed}分钟诶……\n就准备放弃了吗？驳回驳回！",
                f"时间没到呢，离最早宣布放弃时限还有{min_turtle_minutes-time_passed}分钟！"
            ])
            raise ValueError(dmesg)
        await end_game("break", gruop_id, bot, user_id, user_nick)
        return
    except ValueError as err:
        await matcher.send(str(err), reply_message=True)
    except Exception as err:
        await matcher.send(traceback.format_exc(), reply_message=True)

@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    global data
    session_id = str(ev.get_session_id())
    if 'group' in session_id:
        split_id = session_id.split("_")
        user_id = split_id[2]
        gruop_id = split_id[1]
    else:
        user_id = session_id
        gruop_id = None
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  "," ")) != src:
        src = tmpa
    user_2fa_digit = src[:6]
    if not totp_verify(_2fa_key, user_2fa_digit):
        await superuser_debug.finish('2fa verification failed')
    src = src[6:].strip()
    user_nick = ev.sender.card or ev.sender.nickname
    if src == 'reset':
        await daily_clear()
        res = '刷新一天：命令执行成功'
    elif src == 'save':
        await save_to_json()
        res = '存档：命令执行成功'
    elif src == 'backup':
        await save_data_backup()
        res = '备份：命令执行成功'
    elif src == 'load':
        await load_json()
        res = '读档：命令执行成功'
    elif src[:6] == 'await ':
        try:
            try: res = await eval(src[6:])
            except: res = await exec(src[6:])
        except Exception as err:
            res = '出错了: ' + repr(err)
        else:
            res = '命令执行成功' if not res else str(res)
    else:
        try:
            try: res = eval(src)
            except: res = exec(src)
        except Exception as err:
            res = '出错了: ' + repr(err)
        else:
            res = '命令执行成功' if not res else str(res)
    await superuser_debug.finish(res, reply_message = True)
