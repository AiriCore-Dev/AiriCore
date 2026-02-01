import os
import re
import json
import time
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
group_is_tamed = {}
emoji_dir = os.path.join(os.path.dirname(__file__), 'emoji')
emoji_list = [os.path.join(emoji_dir, x) for x in os.listdir(emoji_dir)]

memory_group = {}

memory_max_capability_group = 200

async def call_llm(role_setup, input_words):
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
        max_completion_tokens=500,
        temperature=0.46,
        top_p=0.88,
        stream=False,
        stop=None,
        frequency_penalty=0.7,
        presence_penalty=0.1,
        extra_body={
            "thinking": {"type": "disabled"}
        }
    ) 
    return json.loads(completion.model_dump_json())["choices"][0]["message"]["content"].split('*')

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
    if mode:
        await asyncio.sleep(random.randint(60,7200))
    role_setup_1 = role_setup+"\n\n【以下是上下文，供参考，格式为 发言人: 发言内容】\n"+'\n'.join(memory_group[gruop_id])+"\n\n现在的时间是："+str(int(time.time()))+"\n现在轮到你主动发言，请充分参考并结合上下文内容以及发言的时间，继续之前的话题，发表自己的看法。"
    msg_list = await call_llm(role_setup_1, "")
    if not len(msg_list[0]): return
    
    await save_memory(gruop_id, "(你)", '，'.join(msg_list))
    
    if random.randint(1,5) == 1:
        sticker = await generate_random_emoji()
        await airi_llm.send(sticker)
        await asyncio.sleep(random.randint(1,5))        
    for msgid in range(len(msg_list)):
        if len(msg_list[msgid]):
            await airi_llm.send(msg_list[msgid])
        need_reply = 0
        await asyncio.sleep(random.randint(3,5) if msgid != len(msg_list)-1 else random.randint(1,2))
    if random.randint(1,5) == 1:
        sticker = await generate_random_emoji()
        await airi_llm.send(sticker)
        

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
        
        user_nick = await bot.get_group_member_info(group_id=gruop_id, user_id=user_id)
        user_nick = (user_nick.get("nickname") or user_nick.get("card") or user_id)
        
        input_words = str(ev.message).strip()
        input_words = re.sub(r"\[CQ:image.*?\]", "", input_words)
        
        await save_memory(gruop_id, user_nick, input_words)
        
        if random.randint(1,300) == 1:
            await passive_speaking(gruop_id, 1)

        try:
            if user_id in superusers and input_words.startswith("."):
                input_words = input_words[4:]
            else:
                assert(not random.randint(0,99))
        except:
            return
        
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
        
        role_setup_1 = role_setup+"\n\n【以下是上下文，供参考，格式为时间: 发言人: 发言内容】\n"+'\n'.join(memory_group[gruop_id])+"\n\n当前提问者的名字："+user_nick
        msg_list = await call_llm(role_setup_1, input_words)
        if not len(msg_list[0]): return
        
        await save_memory(gruop_id, "(你)", '，'.join(msg_list))
        
        if random.randint(1,5) == 1:
            sticker = await generate_random_emoji()
            await airi_llm.send(sticker)
        for msgid in range(len(msg_list)):
            if len(msg_list[msgid]):
                await airi_llm.send(msg_list[msgid], reply_message=True if need_reply else False)
            need_reply = 0
            await asyncio.sleep(random.randint(3,5) if msgid != len(msg_list)-1 else random.randint(1,2))
        if random.randint(1,5) == 1:
            sticker = await generate_random_emoji()
            await airi_llm.send(sticker)
        
    except Exception as err:
        print(err)
        #await airi_llm.send(str(err), reply_message=True)

    group_is_tamed[gruop_id] = 0