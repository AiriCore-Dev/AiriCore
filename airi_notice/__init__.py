import datetime
import nonebot
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent

BLACKLIST = []
gr_name = {}

query_tmxx_status = on_message(priority=1,block=False)

@query_tmxx_status.handle()
async def query_tmxx_status_func(bot: Bot, ev: MessageEvent):
    global BLACKLIST, gr_name
    
    if (len(str(ev.get_session_id()).split('_')) != 1) and str(ev.get_session_id()).split('_')[1] in BLACKLIST: return
    msg = str(ev.message)

    tmxx_is_mentioned = 0
    
    keywords = []
    for keyword in keywords:
        if keyword in msg:
            tmxx_is_mentioned = 1
            break
    if tmxx_is_mentioned:
        cur_time = datetime.datetime.now()
        session_id = str(ev.get_session_id())
        if 'group' in session_id:
            split_id = session_id.split('_')
            qq_id = split_id[2]
            gruop_id = split_id[1]
        else:
            qq_id = session_id
            gruop_id = None

        user_nick = await bot.get_group_member_info(group_id=gruop_id, user_id=qq_id)
        user_nick = (user_nick.get("card") or user_nick.get("nickname") or qq_id)
        
        try:
            gr_name[bot.self_id]
        except:
            gr_name[bot.self_id] = {}
            gr_list = await bot.get_group_list()
            for gr in gr_list:
                gr_name[bot.self_id][gr["group_id"]] = gr["group_name"]
                
        mesg = '📣 新消息提醒\n🕗 {}\n👨‍ {}({})\n📀 {}({})\n📩 {}'.format(str(cur_time)[:-7], user_nick, qq_id, gr_name[bot.self_id][int(gruop_id)], gruop_id, msg.replace('[CQ:at,qq=]','@'))
        await bot.send_private_msg(user_id=864623174,message=mesg)
