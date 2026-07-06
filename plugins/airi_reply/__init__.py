import os
import time
import base64
from nonebot import on_fullmatch, on_startswith
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent

async def localpath_to_base64(pth):
    pth = os.path.join(os.path.dirname(__file__), pth)
    with open(pth,"rb") as fil:
        byt = fil.read()
    return "base64://" + base64.b64encode(byt).decode() 

last_notice = 0
reply_interval = 60

dklmt = on_startswith(('打卡啦摩托','打卡拉摩托','大卡拉摩托','大卡啦摩托'), priority=99)
wdh = on_startswith(('汪大吼','wonderhoi','wonderhoy','わんだほ~い '), priority=99,ignorecase=True)

@dklmt.handle()
async def _(bot: Bot, ev: MessageEvent):
    global last_notice
    if time.time() - last_notice > reply_interval:
        last_notice = time.time()
        msg = await localpath_to_base64('dklmt.wav')
        message = MessageSegment.record(msg)   
        await dklmt.send(message)
    
@wdh.handle()
async def _(bot: Bot, ev: MessageEvent):
    global last_notice
    if time.time() - last_notice > reply_interval:
        last_notice = time.time()
        msg = await localpath_to_base64('wdh.wav')
        message = MessageSegment.record(msg)
        await wdh.send(message)
