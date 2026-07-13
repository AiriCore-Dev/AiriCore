import os
import json
import time
from openai import AsyncOpenAI
from .constants import bot_nick, llm_api_key, llm_base_url, other_llm_model
from . import state

with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils', 'generate_turtle_soup_prompt.md'), 'r', encoding='utf-8') as f:
    generate_turtle_soup_prompt = f.read()
with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils', 'turtle_soup_question_prompt.md'), 'r', encoding='utf-8') as f:
    turtle_soup_question_prompt = f.read()
with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils', 'turtle_soup_truth_prompt.md'), 'r', encoding='utf-8') as f:
    turtle_soup_truth_prompt = f.read()
with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils', 'turtle_soup.json'), 'r', encoding='utf-8') as f:
    turtle_soup = json.load(f)

client = AsyncOpenAI(
    api_key=llm_api_key,
    base_url=llm_base_url
)

async def call_llm(prompt, input, deepseek):
    completion = await client.chat.completions.create(
        model=other_llm_model,
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
        max_completion_tokens=4096,
        temperature=0.1,
        top_p=0.3,
        stream=False,
        stop=None,
    )
    return json.loads(completion.model_dump_json())["choices"][0]["message"]["content"]

async def check_data_existance(gruop_id, user_id):
    try:
        state.data['group']
    except:
        state.data['group'] = {}
    try:
        state.data['player']
    except:
        state.data['player'] = {}
    try:
        state.data['group'][gruop_id]
    except:
        state.data['group'][gruop_id] = {"times": 0, "has_played": []}
    try:
        state.data['player'][user_id]
    except:
        state.data['player'][user_id] = {"rank": 0}
    if 'turtle' in state.data['group'][gruop_id]:
        try:
            state.data['group'][gruop_id]['turtle']['players'][user_id]
        except:
            state.data['group'][gruop_id]['turtle']['players'][user_id] = {'query_trial': 0, 'truth_trial': 0}

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

async def generate_help_message(bot, max_player_query_trial, max_player_truth_trial, max_group_trial, min_turtle_minutes, max_group_turtle_perday):
    msg = []
    res = '\
🐢 Momoi Airi Turtle Soup\n\
你已经猜到结局了吗？\n\
一个人也能玩的海龟汤推理故事\n\
海龟汤中虽然会告诉你故事结局，\n但也许会好奇"为什么会这样啊？"……'
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
海龟汤是一款趣味情境推理游戏，出题人先给出一段简短悬疑的故事结局（汤面），玩家通过提出封闭式问题推进推理，出题人仅以"是""否"作答，玩家需根据回答拼凑线索，最终还原整个故事的完整脉络（汤底）。'
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

async def end_game(mode, gruop_id, bot, user_id, user_nick, max_group_trial, matcher):
    if mode == "trial_off":
        msg = f'❌ 总轮询次数已超过{max_group_trial}次，游戏结束！\n太失败了，怎么这么久都没猜出来……'
    elif mode == "victory":
        msg = f"🧩 PURE MEMORY\n恭喜{user_nick}完成最后一块记忆拼图\n\n【汤底】\n{turtle_soup[state.data['group'][gruop_id]['turtle']['soup_id']]['truth']}"
        if state.data['group'][gruop_id]['turtle']['soup_id'] not in state.data['group'][gruop_id]['has_played']:
            state.data['group'][gruop_id]['has_played'].append(state.data['group'][gruop_id]['turtle']['soup_id'])
    elif mode == "break":
        msg = f'🚫 发起者终止了本次游戏'
    history_msg = await construct_turtle_soup_history(bot.self_id, bot_nick, msg)
    state.data['group'][gruop_id]['turtle']['history'].append(history_msg)
    await matcher.send(f'{msg}\n\n以下是历史记录：')
    await bot.send_group_forward_msg(group_id=gruop_id, messages=state.data['group'][gruop_id]['turtle']['history'])
    del state.data['group'][gruop_id]['turtle']
