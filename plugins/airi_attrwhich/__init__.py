import aiohttp

from nonebot.adapters.onebot.v11 import Message
from nonebot.params import T_State
from nonebot.plugin import on_endswith
from nonebot.adapters.onebot.v11 import Bot,Event
from nonebot.rule import to_me

async def get_sx(word):
    url = "https://lab.magiconch.com/api/nbnhhsh/guess"

    headers = {
        'origin': 'https://lab.magiconch.com',
        'referer': 'https://lab.magiconch.com/nbnhhsh/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36',
    }
    data = {
        "text": f"{word}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url=url, headers=headers, data=data) as resp:
            msg = await resp.json()
            return msg if msg else []


sx = on_endswith("是什么", rule=to_me())


@sx.handle()
async def _(bot: Bot,event: Event):
    msg = str(event.get_message())[:-3]
    data = await get_sx(msg)
    result = ""
    if not data:
        await sx.finish(message=f"没有找到缩写 {msg} 的意思呢～")
    try:
        data = data[0]
        name = data['name']
        try:
            content = data['trans']
            result += ' , '.join(content)
        except KeyError:
            pass
        try:
            inputs = data['inputting']
            result += ', '.join(inputs)
        except KeyError:
            pass
        if result:
            await sx.finish(message=name + "：" + result)
        await sx.finish(message=f"没有找到缩写 {msg} 的意思呢～")
    except KeyError:
        return


