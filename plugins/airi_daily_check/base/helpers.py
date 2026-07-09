import base64
import random
import hashlib
import datetime
from io import BytesIO

import httpx
from PIL import Image
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent

from . import state
from . import cache
from .constants import asset, NOT_REGISTERED_TIP
from .matchers import qiandao


def parse_session(ev: MessageEvent):
    session_id = str(ev.get_session_id())
    if 'group' in session_id:
        parts = session_id.split('_')
        return parts[2], parts[1]
    return session_id, None


async def resting_guard(reply_message: bool = True) -> bool:
    notice = await check_anytime()
    if not notice:
        return False
    if random.randint(1, 3) == 1:
        await qiandao.finish(notice, reply_message=reply_message)
    return True


async def ensure_registered(matcher, user_id):
    if user_id not in state.data:
        await matcher.finish(NOT_REGISTERED_TIP, reply_message=True)


async def check_anytime():
    hour = datetime.datetime.now().hour
    if hour > 21:
        return "慢慢长夜，该睡觉啦～（哈啊）\n祝你做一个美好的梦！\n明天早上6点之后再来找我吧！晚安！"
    elif hour < 6:
        return "Zzz......\n（airi似乎正在睡觉）\n旁边有一张字条：\n熬夜伤身体，请一定要早睡！\n闹钟上的定时：6:00 AM"
    return ""


async def download_avatar(uid: str) -> bytes:
    cached = cache.get("user_avatar", uid, ttl=cache.TTL_AVATAR)
    if cached:
        return cached
    url = f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=640"
    datad = await download_url(url)
    if not datad or hashlib.md5(datad).hexdigest() == "acef72340ac0e914090bd35799f5594e":
        url = f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100"
        datad = await download_url(url)
    if datad:
        cache.put("user_avatar", uid, datad)
    return datad


async def download_url(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        for i in range(3):
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                return resp.content
            except Exception as e:
                print(f"Error downloading {url}, retry {i}/3: {str(e)}")


def image_to_base64(img) -> str:
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return "base64://" + base64.b64encode(buf.getbuffer()).decode()


async def localpath_to_base64(pth):
    def _build():
        with open(pth, "rb") as fil:
            byt = fil.read()
        return "base64://" + base64.b64encode(byt).decode()

    return cache.get_or_build("localpath_b64", pth, _build, stat_path=pth)


async def acquire_jrys(user_id):
    if not state.data[user_id]['jrys']:
        state.data[user_id]['jrys'] = random.randint(1, 80)
    return asset('utils', 'jrys', f'{state.data[user_id]["jrys"]}.png')


async def get_sticker(x, user_id, mode=1):
    theme = state.data[user_id]['theme']
    if theme not in state.theme_extension:
        state.theme_extension[theme] = open(asset('stickers', theme, 'extension')).read()
    return asset('stickers', theme, '{}.{}'.format(x, state.theme_extension[theme]))


def _make_250px_kernel(img, mode=0):
    if mode:
        res = Image.new('RGBA', (250, 250), (255, 255, 255, 1))
    else:
        res = Image.new('RGBA', (250, 250), (0, 0, 0, 0))
    x1, y1 = img.size
    img = img.convert('RGBA')
    if x1 > y1:
        img = img.resize((250, tmp := 250 * y1 // x1))
        y1 = (250 - tmp) // 2
        res.paste(img, (0, y1), mask=img.split()[3])
    else:
        img = img.resize((tmp := 250 * x1 // y1, 250))
        x1 = (250 - tmp) // 2
        res.paste(img, (x1, 0), mask=img.split()[3])
    return res, res.split()[3]


async def make_250px(img, mode=0):
    return _make_250px_kernel(img, mode)


async def make_250px_cached(path, mode=0):
    return cache.get_or_build(
        "sticker_250", (path, mode),
        lambda: _make_250px_kernel(Image.open(path).convert('RGBA'), mode),
        stat_path=path,
    )


def _build_new_sticker(stk, mode):
    new_mask = cache.get_image(asset('utils', 'new.png'))
    if mode:
        meme, _ = _make_250px_kernel(Image.open(stk).convert('RGBA'), 1)
    else:
        meme = Image.open(stk).convert('RGBA')
    if meme.size[0] / meme.size[1] > new_mask.size[0] / new_mask.size[1]:
        new_mask = new_mask.resize((meme.size[1] // 2 * new_mask.size[0] // new_mask.size[1], meme.size[1] // 2))
    else:
        new_mask = new_mask.resize((meme.size[0] // 2, meme.size[0] // 2 * new_mask.size[1] // new_mask.size[0]))
    meme.paste(new_mask, (0, 0), mask=new_mask.split()[3])
    if mode:
        return meme
    return image_to_base64(meme.convert('RGB'))


async def generate_new_sticker(x, user_id, mode=0):
    stk = await get_sticker(x, user_id)
    return cache.get_or_build(
        "new_sticker", (stk, mode), lambda: _build_new_sticker(stk, mode),
        stat_path=stk,
    )


def acquire_sticker(user_id, x):
    if x not in state.data[user_id]['collections']:
        state.data[user_id]['collections'].append(x)
        return 1
    return 0


async def unlock_segment(user_id, sticker_id, text):
    new_sticker = await generate_new_sticker(sticker_id, user_id)
    return MessageSegment.text(text) + MessageSegment.image(new_sticker)


async def check_all_achiv(user_id, bot: Bot, ev: MessageEvent):
    if state.data[user_id]['need_reborn']:
        return
    if any(i not in state.data[user_id]['collections'] for i in range(1, 101)):
        return
    for j in range(101, 107):
        if j not in state.data[user_id]['collections']:
            break
    state.data[user_id]['need_reborn'] = 1
    if j == 106:
        msg = MessageSegment.text('\n✅ 恭喜你完成了全收藏！\nAiri给你比一个心哦！')
    elif acquire_sticker(user_id, j):
        new_sticker = await generate_new_sticker(j, user_id)
        msg = MessageSegment.text(
            '\n✅ 恭喜你集齐了1-100号收藏品！\nAiri给你比一个心哦！\n📦 获得第{}号创世收藏品\n🎉是NEW，好耶！🎉\n'.format(j)
        ) + MessageSegment.image(new_sticker)
        if j < 105:
            msg += f"\n长路漫漫……离真正的全收藏还差{105 - j}轮轮回！"
        else:
            msg += f"\n恭喜你完成了全收藏！你过关！"
    await bot.send(message=msg, event=ev, at_sender=True)
