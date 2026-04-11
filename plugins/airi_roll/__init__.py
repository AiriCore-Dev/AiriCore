from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from random import randint

airi_roll = on_command("roll", priority=99)

@airi_roll.handle()
async def main(bot: Bot, ev: MessageEvent):
    #await airi_roll.finish('11',reply_message = True)
    msg = str(ev.message).split()
    if len(msg) == 1:
        res = str(randint(1,100))
    elif len(msg) == 3:
        try:
            a = int(msg[1])
            b = int(msg[2])
        except:
            res = '请输入正确的数字！'
        else:
            res = str(randint(a,b)) if a<b else str(randint(b,a))
    else:
        res ="用法：\nroll: 抽1-100随机数字\nroll x y: 抽x-y之间随机数字"
    await airi_roll.finish(res,reply_message = True)
    #await airi_roll.finish('11',reply_message = True)
