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
from .kokomi_llm import kokomi_llm
from .message_parser import parse_to_command

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
            need_apply_llm = 0
            if msg.startswith("船长"):
                msg = await kokomi_llm(msg[2:])
                if msg[0]:
                    need_apply_llm = 1
                    msg = msg[1]
                    llm_msg = msg + "\n"
                else:
                    await wws_bot.send(msg[1], reply_message=True)
                    return
            # 解析快捷指令 -> 分发用 split_msg
            action, payload = parse_to_command(msg)
            if action == 'stop':
                return
            elif action == 'reply':
                await bot.send(ev, payload, reply_message = True)
                return
            split_msg = payload
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
            msg_res = MessageSegment.text(llm_msg if need_apply_llm else "")
            if fun['type'] == 'msg':
                await wws_bot.send(msg_res + MessageSegment.text(fun['msg']),reply_message = True)
            # 发送图片消息
            elif fun['type'] == 'img':
                await wws_bot.send(msg_res + MessageSegment.image(fun['img']),reply_message = True)
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
