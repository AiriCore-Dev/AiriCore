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
reply_interval = 10

dklmt = on_startswith(('打卡啦摩托','打卡拉摩托','大卡拉摩托','大卡啦摩托'), priority=99)
wdh = on_startswith(('汪大吼','wonderhoi','wonderhoy','わんだほ~い '), priority=99,ignorecase=True)
ngg = on_startswith("你过关", priority=99)
cgdz = on_startswith("闯关弟子注意", priority=99)
ncddl = on_startswith("你从丹东来", priority=99)
erika = on_startswith("erika", priority=99)
nkddw = on_startswith("大哥", priority=99)

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

@ngg.handle()
async def _(bot: Bot, ev: MessageEvent):
    global last_notice
    if time.time() - last_notice > reply_interval:
        last_notice = time.time()
        msg = await localpath_to_base64('ngg.wav')
        message = MessageSegment.record(msg)
        await ngg.send(message)
        
@cgdz.handle()
async def _(bot: Bot, ev: MessageEvent):
    global last_notice
    if time.time() - last_notice > reply_interval:
        last_notice = time.time()
        msg = await localpath_to_base64('cgdz.wav')
        message = MessageSegment.record(msg)
        await cgdz.send(message)

@ncddl.handle()
async def _(bot: Bot, ev: MessageEvent):
    global last_notice
    if time.time() - last_notice > reply_interval:
        last_notice = time.time()
        msg = await localpath_to_base64('ncddl.wav')
        message = MessageSegment.record(msg)
        await ncddl.send(message)

@erika.handle()
async def _(bot: Bot, ev: MessageEvent):
    global last_notice
    if time.time() - last_notice > reply_interval:
        last_notice = time.time()
        msg = await localpath_to_base64('erika.mp3')
        message = MessageSegment.record(msg)
        await erika.send(message)

@nkddw.handle()
async def _(bot: Bot, ev: MessageEvent):
    global last_notice
    if time.time() - last_notice > reply_interval:
        last_notice = time.time()
        msg = await localpath_to_base64('nkddw.mp3')
        message = MessageSegment.record(msg)
        await erika.send(message)
