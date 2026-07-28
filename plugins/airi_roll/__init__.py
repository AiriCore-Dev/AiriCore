from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.adapters.onebot.v11.event import MessageEvent
from random import randint

USAGE = "用法：\nroll: 抽1-100随机数字\nroll x y: 抽x-y之间随机数字"

airi_roll = on_command("roll", priority=99)


@airi_roll.handle()
async def main(bot: Bot, ev: MessageEvent, arg: Message = CommandArg()):
    args = arg.extract_plain_text().split()
    if not args:
        res = str(randint(1, 100))
    elif len(args) == 2:
        try:
            a = int(args[0])
            b = int(args[1])
        except ValueError:
            res = '请输入正确的数字！'
        else:
            res = str(randint(a, b)) if a < b else str(randint(b, a))
    else:
        res = USAGE
    await airi_roll.finish(res, reply_message=True)
