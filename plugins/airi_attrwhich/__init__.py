import aiohttp

from nonebot.plugin import on_endswith
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.rule import to_me

TIMEOUT = aiohttp.ClientTimeout(total=10)


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
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(url=url, headers=headers, data=data) as resp:
                msg = await resp.json(content_type=None)
                return msg if isinstance(msg, list) else []
    except Exception:
        return []


sx = on_endswith("是什么", rule=to_me())


@sx.handle()
async def _(bot: Bot, event: Event):
    text = event.get_message().extract_plain_text().strip()
    if not text.endswith("是什么"):
        return
    msg = text[:-3].strip()
    if not msg:
        return
    data = await get_sx(msg)
    if not data:
        await sx.finish(message=f"没有找到缩写 {msg} 的意思呢～")
    entry = data[0]
    if not isinstance(entry, dict) or "name" not in entry:
        await sx.finish(message=f"没有找到缩写 {msg} 的意思呢～")
    parts = []
    for key in ("trans", "inputting"):
        vals = entry.get(key)
        if vals:
            parts.append(" , ".join(str(v) for v in vals))
    if parts:
        await sx.finish(message=entry["name"] + "：" + " / ".join(parts))
    await sx.finish(message=f"没有找到缩写 {msg} 的意思呢～")
