import os
import base64
import asyncio
import nonebot
from utils.totp_2fa import totp_verify	
from nonebot import on_notice, on_command, get_driver
from nonebot.permission import SUPERUSER
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import GroupIncreaseNoticeEvent, Message
from nonebot.adapters.onebot.v11.bot import Bot, MessageSegment

driver = get_driver()
_2fa_key = getattr(driver.config, "_2fa_key", "")

def localpath_to_base64(pth):
    if not os.path.exists(pth):
        raise FileNotFoundError(f"图片文件不存在: {pth}")
    with open(pth, "rb") as fil:  
        byt = fil.read()
    return "base64://" + base64.b64encode(byt).decode() 

intro = """Lovely！Fairy！Momoi Airi！
本Bot是一款基于 AiriCore 的高性能QQ群Bot，功能请发送 help 查看。
Bot一群：1030569383
Bot二群：808085026
AiriCore Dev群：1051523491
Bot官网：www.airi.asia
本Bot是完全公益的，不接受任何形式的收费和赞助。如果你遇到收费拉群、索要赞助等情况，请联系bot主举报！
bot主联系邮箱：saki@saki.ln.cn
"""

try:
    img = localpath_to_base64(os.path.join(os.path.dirname(__file__), 'airi.jpg'))
    duang = localpath_to_base64(os.path.join(os.path.dirname(__file__), 'duang.wav'))
    msg = MessageSegment.text(intro) + MessageSegment.image(img)
except Exception as e:
    print(f"警告：图片加载失败 - {e}")
    msg = MessageSegment.text(intro) 

bot_whitelist = ["2745762139", "1330248395", "535071478"]

group_increase = on_notice(priority=5, block=False)

@group_increase.handle()
async def handle_group_increase(bot: Bot, event: GroupIncreaseNoticeEvent):
    try:
        bot_id = str(bot.self_id)
        user_id = str(event.user_id)
        
        if user_id == bot_id:
            group_id = event.group_id
            bot_list = list(nonebot.get_bots().values())
            bot_list = [str(x.self_id) for x in bot_list]
            group_member_list = await bot.get_group_member_list(group_id=group_id)
            group_member_list = [str(x['user_id']) for x in group_member_list]
            
            target_bots = []
            for botq in bot_list:
                if botq in group_member_list and botq != bot_id:
                    target_bots.append(botq)
            
            if bot_id in bot_whitelist or not len(target_bots):
                await bot.send_group_msg(group_id=group_id, message=MessageSegment.record(duang))
                await bot.send_group_msg(group_id=group_id, message=msg)
            else:
                await bot.send_group_msg(group_id=group_id, message=f"该群已存在AiriCore分布式账号（{', '.join(target_bots)}），即将退群")
                await bot.set_group_leave(group_id=group_id)
                
    except Exception as e:
        print(f"处理入群事件时发生错误：{str(e)}")


airi_full_group = on_command('airifullgroup', priority=5, block=True, permission=SUPERUSER)

@airi_full_group.handle()
async def _(bot: Bot, arg: Message = CommandArg()):
    # 解析参数：第一个词为2fa码，剩余为消息内容
    args = arg.extract_plain_text().strip().split(maxsplit=1)


    digit = args[0].strip()
    if len(args) < 2:
        msg_content = ""
    else:
        msg_content = args[1].strip()
    
    # 2FA 验证
    if not totp_verify(_2fa_key, digit):
        await airi_full_group.finish("2fa verification failed")
    
    # 构造消息
    target_msg = Message(msg_content) if len(msg_content) else msg
    
    for bot_instance in nonebot.get_bots().values():
        gr_list = await bot_instance.get_group_list()
        for gr in gr_list:
            try:
                await bot_instance.send_group_msg(group_id=gr["group_id"], message=target_msg)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"发送群消息失败（群{gr['group_id']}）：{e}")