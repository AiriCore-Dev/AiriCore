from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

haruki_help = on_command("pjskhelp", priority=99)

@haruki_help.handle()
async def main(bot: Bot, ev: MessageEvent):
    message = MessageSegment.text("\
Haruki帮助文档：\n\
https://docs.shiromiku.moe/")
    await haruki_help.send(message)
