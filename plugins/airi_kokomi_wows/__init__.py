from .config import Plugin_Config
from .log.error_log import write_error
from .load_fonts import fonts
from .path import plugin_path
from .scripts import (
    call_api,
    clan_tag,
    dog_tag,
    time_zone
)
from .data_source import (
    Authorization,
    Picture,
    Game_Data,
    Text_Data,
    Box_Data
)
import traceback
from nonebot import on_command, on_startswith
from nonebot.adapters.onebot.v11 import (
    ActionFailed,
    Bot,
    MessageEvent,
    MessageSegment,
)
from nonebot.log import logger
from .command_select import select_funtion
from .kokomi_chs import *
import os
import json
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key="sk-c8hddt5pd43l14mp5gfpsjdjkw5q5d2btuk7vwxaycwznqsd",
    base_url="https://api.xiaomimimo.com/v1"
)

with open(os.path.join(os.path.dirname(__file__), 'kokomi_setup.txt'),'r',encoding='utf-8') as f:
    role_setup = f.read()

async def kokomi_llm(input_words): 
    try:    
        completion = await client.chat.completions.create(
            model="mimo-v2-flash",
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
            max_completion_tokens=1024,
            temperature=0,
            top_p=1,
            stream=False,
            stop=None,
            frequency_penalty=0,
            presence_penalty=0,
            extra_body={
                "thinking": {"type": "disabled"}
            }
        )
        
        msg_list = json.loads(completion.model_dump_json())["choices"][0]["message"]["content"].split(':')
        if len(msg_list) == 2:
            msg_list = [int(msg_list[0]),msg_list[1]]
            return msg_list
        else:
            raise ValueError("服务器繁忙，请稍后再试")
    except Exception as err:
        return [0,str(err)]

wws_bot = on_startswith(trigger_list + trigger_shortcut_list, ignorecase=True)

@wws_bot.handle()
async def main(bot: Bot, ev: MessageEvent):
    tot = 0
    while 1:
        try:
            session_id = str(ev.get_session_id())
            # 判断消息类型，私聊/群聊
            if 'group' in session_id:
                split_id = session_id.split('_')
                qq_id = split_id[2]
                gruop_id = split_id[1]
            else:
                qq_id = session_id
                gruop_id = None
            # 黑名单
            if qq_id in Plugin_Config.BLACKLIST_USER:
                await wws_bot.finish("数据请求异常，请稍后再试。", reply_message = True)
            if gruop_id:
                if gruop_id in Plugin_Config.BLACKLIST:
                    return
            msg = str(ev.message).lower()
            # Kokomi_LLM
            if msg.startswith("船长"):
                msg = await kokomi_llm(msg[2:])
                if msg[0]:
                    msg = msg[1]
                else:
                    await wws_bot.finish(msg[1])
            # 国服id带空格的特殊处理
            if 'wws bind cn ' in msg or 'wws bind 国服 ' in msg:
                split_msg = ['wws', 'bind', 'cn', msg[12:]]
            else:
                split_msg = msg.split()  # 按空格分隔消息
            if Plugin_Config.EN_START_WITH == split_msg[0]:
                del split_msg[0]
            if Plugin_Config.EN_START_WITH == split_msg[0][0]:
                split_msg[0] = split_msg[0].replace(Plugin_Config.EN_START_WITH,'')
            # 快捷指令
            if split_msg[0][:6] == 'recent' and split_msg[0] != 'recents':
                if len(split_msg) == 1:
                        if split_msg[0] == 'recent':
                            split_msg = ['wws', 'me', 'recent']
                        else:
                            try: recent_days = int(split_msg[0][6:])
                            except: return
                            else: split_msg = ['wws', 'me', 'recent', str(recent_days)]
                elif split_msg[1] in ['on','off','开','关'] and len(split_msg) == 2:
                    split_msg_tmp = ['wws', 'recent']
                    split_msg_tmp.append(split_msg[1])
                    split_msg = split_msg_tmp
                else:
                    try:
                        int(split_msg[1])
                    except:
                        await bot.send(ev, f"recent天数错误！",reply_message = True)
                        return
                    if int(split_msg[1]) < 1:
                        await bot.send(ev, f"recent天数错误！",reply_message = True)
                        return
                    split_msg_tmp = ['wws', 'me', 'recent']
                    split_msg_tmp.append(split_msg[1])
                    split_msg = split_msg_tmp
            elif split_msg[0][:4] == '看看我的':
                if len(split_msg) == 1:
                    if split_msg[0] == '看看我的':
                        return
                    split_msg_tmp = ['wws', 'me', 'ship']
                    split_msg_tmp.append(split_msg[0][4:])
                    split_msg = split_msg_tmp
                else:
                    ship_name_tmp = split_msg[0][4:]
                    for i in range(1,len(split_msg)):
                        ship_name_tmp += split_msg[i]
                    split_msg_tmp = ['wws', 'me', 'ship']
                    split_msg_tmp.append(ship_name_tmp)
                    split_msg = split_msg_tmp
            elif split_msg[0] == '绑定账号':
                if len(split_msg) != 3:
                    await bot.send(ev, f"格式不正确！\n格式：绑定账号 服务器 ID",reply_message = True)
                    return
                else:
                    split_msg_tmp = ['wws', 'bind']
                    split_msg_tmp.append(split_msg[1])
                    split_msg_tmp.append(split_msg[2])
                    split_msg = split_msg_tmp                
            elif len(split_msg) == 1 and split_msg[0][0] != Plugin_Config.EN_START_WITH:
                if split_msg[0] == '看看我':
                    split_msg = ['wws', 'me']
                elif split_msg[0] == '好好看看我':
                    split_msg = ['wws', 'me', 'info']
                elif split_msg[0] == '查看全部战绩':
                    split_msg = ['wws', 'me', 'ships', 'all']
                elif split_msg[0] == 'recents':
                    split_msg = ['wws', 'me', 'recents']
                else:
                    return
            # 消息 -> 函数
            if len(split_msg) > 1 and (split_msg[0]+' ' in trigger_list):
                split_msg[0] = 'wws'
            fun = await select_funtion.main(
                msg=split_msg,
                user_id=qq_id,
                user_data={},
                platform=Plugin_Config.BOT_PLATFORM,
                platform_id='123456',
                channel_id='123456',
                platform_data={}
            )
            # 发送文字消息
            if fun['type'] == 'msg':
                await wws_bot.send(fun['msg'],reply_message = True)
            # 发送图片消息
            elif fun['type'] == 'img':
                await wws_bot.send(MessageSegment.image(fun['img']),reply_message = True)
            return
        except ActionFailed:
            return False
        except Exception as e:
            tot += 1
            if tot > 2:
                logger.error(traceback.format_exc())
                await bot.send(ev, f"Error: {type(e).__name__}")
                return
            else:
                continue