import os
import re
import json
import time
import string
import random
import base64
import asyncio
import nonebot
import traceback
from openai import AsyncOpenAI
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot import get_driver, on_message, require, on_startswith
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

role_setup = ""
def flush_prompt():
    global role_setup
    with open(os.path.join(os.path.dirname(__file__), 'airi_setup.txt'),'r',encoding='utf-8') as f:
        role_setup = f.read()
    return "提示词已刷新"
flush_prompt()

client = AsyncOpenAI(
    api_key="",
    base_url=""
)

whitelist_group_list = []
whitelist_bot_list = []
superusers = []
memory_max_capability_group = 300

group_is_tamed = {}
passive_speaking_group_is_tamed = {}
last_speak_time_group = {}
negative_speaking_tokens_group = {}
emoji_dir = os.path.join(os.path.dirname(__file__), 'emoji')
emoji_list = [os.path.join(emoji_dir, x) for x in os.listdir(emoji_dir)]
puncts = r"，。！？；：～"
mpattern = re.compile(rf"[^{puncts}]+[{puncts}]")
memory_group = {}

async def call_llm(role_setup, input_words):
    try:
        completion = await client.chat.completions.create(
            model="",
            messages=[
                {
                    "role": "system",
                    "content": role_setup
                },
                {
                    "role": "user",
                    "content": input_words
                }
            ],
            max_completion_tokens=100,
            temperature=0.77,
            top_p=1.0,
            stream=False,
            stop=None,
            frequency_penalty=0.1,
            presence_penalty=0.1,
            extra_body={
                "thinking": {"type": "disabled"}
            }
        ) 
        return json.loads(completion.model_dump_json())["choices"][0]["message"]["content"]
    except:
        return ""

async def generate_random_emoji():
    with open(random.choice(emoji_list), 'rb') as f:
        return MessageSegment.image('base64://'+base64.b64encode(f.read()).decode())
        
async def save_memory(gruop_id, speaker, content):
    global memory_group
    try:
        memory_group[gruop_id]
    except:
        memory_group[gruop_id] = []
    memory_group[gruop_id].append(f'{speaker}：{content}')
    if len(memory_group[gruop_id]) > memory_max_capability_group:
        memory_group[gruop_id].pop(0)

airi_llm = on_message(priority=50,block=False)

async def passive_speaking(gruop_id, mode=1):
    global passive_speaking_group_is_tamed, last_speak_time_group, negative_speaking_tokens_group
    try:
        if mode and passive_speaking_group_is_tamed[gruop_id]:
            return
    except:
        pass
    if mode: passive_speaking_group_is_tamed[gruop_id] = 1
    
    if mode:
        await asyncio.sleep(random.randint(301,7200))
    try:    
        if mode and time.time()-last_speak_time_group[gruop_id]<300:
            passive_speaking_group_is_tamed[gruop_id] = 0
            return
    except:
        pass
    last_speak_time_group[gruop_id] = time.time()
    if not negative_speaking_tokens_group[gruop_id]: negative_speaking_tokens_group[gruop_id] = 30
    role_setup_1 = role_setup
    msg_list = await call_llm(role_setup_1, "【以下是上下文，供参考，格式为 发言人: 发言内容】\n"+'\n'.join(memory_group[gruop_id])+"\n\n现在轮到你主动发言，请充分参考并结合上下文内容，继续之前的话题，发表自己的看法。")
    msg_list = re.sub(r"[(（].+?[)）]", "", msg_list)
    
    await save_memory(gruop_id, "(你)", '，'.join(msg_list))
    
    await send_message(msg_list, 0)
    
    if mode: passive_speaking_group_is_tamed[gruop_id] = 0

async def send_message(msg_list, need_reply):
    msg_list = msg_list + "。"
    if random.randint(1,2) == 1:
        msg_list = mpattern.findall(msg_list)
    else:
        msg_list = [msg_list]
    if not len(msg_list):
        return
    is_single = 1
    for msgid in range(len(msg_list)):
        if msg_list[msgid][-1] in ["，","。"]:
            msg_list[msgid] = msg_list[msgid][:-1]
        if len(msg_list[msgid])!=1:
            is_single = 0
    if is_single:
        msg_list = ["！".join(msg_list)+"！"]
    await asyncio.sleep(random.randint(0,5) if len(msg_list)!=1 else random.randint(3,8))
    if random.randint(1,10) == 1:
        sticker = await generate_random_emoji()
        await airi_llm.send(sticker)
        await asyncio.sleep(random.randint(3,10))
    for msgid in range(len(msg_list)):
        if len(msg_list[msgid]):
            if msg_list[msgid][-1] in ["，","。"]:
                msg_list[msgid] = msg_list[msgid][:-1]
            await airi_llm.send(msg_list[msgid], reply_message=True if need_reply else False)
            need_reply = 0
            await asyncio.sleep(random.randint(5,10) if msgid != len(msg_list)-1 else random.randint(1,2))
    if random.randint(1,5) == 1:
        sticker = await generate_random_emoji()
        await airi_llm.send(sticker)
    return need_reply

async def pending_need_speak(bot, ev, gruop_id, user_id):
    global negative_speaking_tokens_group
    if user_id in superusers and str(ev.message).startswith('.'):
        return True
    try:
        if negative_speaking_tokens_group[gruop_id] and (
            'airi' in str(ev.message).lower() or
            '爱莉' in str(ev.message) or
            bot.self_id in str(ev) or
            str(ev.message).startswith('.') or
            str(ev.reply.sender.user_id) == bot.self_id
        ):
            negative_speaking_tokens_group[gruop_id] += 1
            return True
    except:
        pass
    if random.randint(1,200) == 1:
        return True
    return False    

@airi_llm.handle()
async def _(bot: Bot, ev: MessageEvent): 
    global role_setup, group_is_tamed, whitelist_group_list, emoji_list, memory_user, memory_group
    try:
        session_id = str(ev.get_session_id())
        if 'group' in session_id:
            split_id = session_id.split("_")
            user_id = split_id[2]
            gruop_id = split_id[1]
        else:
            user_id = session_id
            gruop_id = None
            
        '''
        if gruop_id not in whitelist_group_list: return
        '''
        if bot.self_id not in whitelist_bot_list: return
        
        try:
            negative_speaking_tokens_group[gruop_id] -= 3
            if negative_speaking_tokens_group[gruop_id]<0:
                negative_speaking_tokens_group[gruop_id] = 0
        except:
            negative_speaking_tokens_group[gruop_id] = 0
        
        user_nick = await bot.get_group_member_info(group_id=gruop_id, user_id=user_id)
        user_nick = (user_nick.get("nickname") or user_nick.get("card") or user_id)
        
        input_words = str(ev.message).strip()
        input_words = re.sub(r"\[CQ:image.*?\]", "", input_words)
        rematch = list(re.finditer(r'\[CQ:at,qq=(\d+)\]', input_words))
        if rematch:
            replace_map = {}
            for match in rematch:
                cqat_str = match.group(0) 
                qq_num = match.group(1)
                user_nick_tmp = await bot.get_group_member_info(group_id=gruop_id, user_id=qq_num)
                user_nick_tmp = (user_nick_tmp.get("nickname") or user_nick_tmp.get("card") or user_id)
                replace_map[cqat_str] = f' @{user_nick_tmp} '
            for old, new in replace_map.items():
                input_words = input_words.replace(old, new)
        
        await save_memory(gruop_id, user_nick, input_words)
        last_speak_time_group[gruop_id] = time.time()
        
        if random.randint(1,150) == 1:
            await passive_speaking(gruop_id, 1)

        need_speak = await pending_need_speak(bot, ev, gruop_id, user_id)
        if not need_speak: return
        
        if input_words.startswith('.'):
            input_words = input_words[1:]
        
        need_reply = random.randint(0,10)//10
        try:
            group_is_tamed[gruop_id]
        except:
            group_is_tamed[gruop_id] = 0
        while group_is_tamed[gruop_id]:
            need_reply = 1
            await asyncio.sleep(3)
            if random.randint(1,20) == 1:
                group_is_tamed[gruop_id] = 0
        group_is_tamed[gruop_id] = 1
        
        if not negative_speaking_tokens_group[gruop_id]: negative_speaking_tokens_group[gruop_id] = 30
        role_setup_1 = role_setup
        msg_list = await call_llm(role_setup_1, "【以下是上下文，供参考，格式为时间: 发言人: 发言内容】\n"+'\n'.join(memory_group[gruop_id])+"\n\n当前发言人的名字："+user_nick+"\n发言内容："+input_words)
        msg_list = re.sub(r"[(（].+?[)）]", "", msg_list)
        
        await save_memory(gruop_id, "(你)", '，'.join(msg_list))
        
        need_reply = await send_message(msg_list, need_reply)
       
    except Exception as err:
        #print(err)
        await airi_llm.send(traceback.format_exc(), reply_message=True)

    group_is_tamed[gruop_id] = 0
