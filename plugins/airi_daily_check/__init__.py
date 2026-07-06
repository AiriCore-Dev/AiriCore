import os
import gc
import re
import bz2
import sys
import json
import time
import math
import hmac
import httpx
import shutil
import pickle
import base64
import random
import hashlib
import nonebot
import asyncio
import requests
import importlib
import subprocess
import datetime
from utils.totp_2fa import totp_verify
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from nonebot import get_driver, on_regex, on_startswith, on_fullmatch, require
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

# --------------------------------------------------------------------------- #
# Globals & configuration
# --------------------------------------------------------------------------- #
timings = require("nonebot_plugin_apscheduler").scheduler
driver = get_driver()
data = {}
theme_extension = {}
hidden_stickers = [17, 13, 37, 20, 100]
game_ans = [0, '', '', '']
_2fa_key = getattr(driver.config, "_2fa_key", "")

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join('data', 'airi_daily_check')
DATA_FILE = os.path.join(DATA_DIR, 'data.pk')

# Difficulty metadata shared by the daily-challenge / flag-submit handlers.
DIFFICULTY = [0, 'NORMAL', 'EXPERT', 'MASTER']
CREDIT_BY_DIFF = [0, 20, 100, 300]

# Hidden hint messages (used by 签到 and 购买提示).
SECRET_MESSAGES = [
    '💬 嘀嘀嘀……我们好像收到一条秘密的摩斯密码！\n-.-..----.-...- -..-...........- -........---.. ---..-...--...- -.....---...-..- ------.--.--..- --...-....-...- -..-.--.-..-.... -....-.---..---- --..-.-..--.--. -....-.---..---- -.-.-..--.....- -........---.- -.---....--...- -.......------.- --...-.-------- -.-..-...--.... .---- --... -.-..------.--- --------.......-',
    '💬 剧烈的大风刮过来一张纸条，这是base64吗？\n6YeN5aSN562+5Yiw5LiA5qyh5Y2z5Y+v6I635b6XMTPlj7fmlLbol4/lk4HvvIzkupTmrKHojrflvpczN+WPt+aUtuiXj+WTge+8gQ==',
    '💬 你正在路上走着，突然跑过来一个瑞典人跟你说：\nMed två tusen poäng kan du låsa upp den hemliga samlingen nummer tjugo!',
    '💬 隐藏Tip: 连续签到7天即可获得100号收藏品！……',
]

NOT_REGISTERED_TIP = '❌ 账号未注册！\n请先签到一次！\n发送“签到”即可'


def asset(*parts):
    """Build a path relative to this plugin's directory."""
    return os.path.join(BASE_DIR, *parts)


def new_account():
    """Return a fresh account record."""
    return {
        'credits': 0,
        'checked_days': 0,
        'collections': [],
        'check_times_daily': 0,
        'receive_transfer_daily': 0,
        'reborn_times': 0,
        "need_reborn": 0,
        "theme": "airi_momo",
        "daily_challenge": [0, 0, 0, 0],
        'jrys': 0,
    }


def load_game_answers():
    """Parse sudoku.txt into the [0, ans1, ans2, ans3] answer table."""
    sdk_data = open(asset('utils', 'sudoku', 'sudoku.txt'), 'r').read().split()
    ans = [0, '', '', '']
    cur = 0
    for i in range(1, 4):
        for j in range(9):
            ans[i] += sdk_data[cur]
            cur += 4 if j == 8 else 10
    return ans


# --------------------------------------------------------------------------- #
# Matchers
# --------------------------------------------------------------------------- #
qiandao = on_fullmatch('签到', priority=10, block=True)
qiandaohelp = on_fullmatch(('签到帮助', '收藏帮助'), priority=10, block=True)
xinxi = on_fullmatch('收藏信息', priority=10, block=True)
shoucang = on_startswith('查看收藏', priority=10, block=True)
chouka = on_startswith('收藏抽卡', priority=10, block=True)
yincang17 = on_fullmatch('给我隐藏收藏品', priority=10, rule=to_me(), block=True)
transcation = on_regex(r'转给.+\d+[个]?积分', priority=10, rule=to_me(), block=True)
reborn = on_startswith('重生', priority=10, rule=to_me(), block=True)
theme_manage = on_startswith('收藏主题', priority=10, block=True)
superuser_debug = on_startswith('qdebug ', priority=10, block=True, rule=to_me(), permission=SUPERUSER)
daily_challenge = on_fullmatch(('每日挑战', '今日挑战'), priority=10, block=True)
flag_submit = on_regex(r'flag{.+}', priority=10, rule=to_me(), block=True)
buy_tip = on_fullmatch('购买提示', priority=10, block=True)
jrys = on_fullmatch(('jrys', '今日运势', '运势'), priority=10, block=True)


# --------------------------------------------------------------------------- #
# Persistence & scheduled jobs
# --------------------------------------------------------------------------- #
@driver.on_startup
async def load_json():
    global data, game_ans
    game_ans = [0, '', '', '']
    try:
        with open(DATA_FILE, 'rb') as f:
            data = pickle.load(f)
    except:
        os.makedirs(DATA_DIR)
        await save_to_json()
    game_ans = load_game_answers()
    gc.collect()


@driver.on_shutdown
async def save_to_json():
    global data
    with open(DATA_FILE, 'wb') as f:
        pickle.dump(data, f)
    gc.collect()


async def daily_clear():
    global data
    should_clear = bool(nonebot.get_bots())
    for i in data.keys():
        if not data[i]['check_times_daily'] and should_clear:
            data[i]['checked_days'] = 0
        data[i]['check_times_daily'] = 0
        data[i]['receive_transfer_daily'] = 0
        data[i]['daily_challenge'] = [0, 0, 0, 0]
        data[i]['jrys'] = 0
    await save_to_json()


async def reset_daily_challenge():
    global game_ans
    while 1:
        try:
            proc = subprocess.Popen(
                asset('utils', 'sudoku', 'sdk_generate_daily.sh'),
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            proc.communicate(timeout=10)
        except:
            proc.kill()
            os.system('pkill -9 sudoku')
            continue
        else:
            os.system('pkill -9 sudoku')
            break

    sdk_data = open(asset('utils', 'sudoku', 'game.txt'), 'r').read().split()
    game_data = [0, sdk_data[:81], sdk_data[84:165], sdk_data[168:249]]
    font = ImageFont.truetype(font=asset('utils', 'font.ttc'), size=60)
    nows = datetime.datetime.now()
    nows = '{}-{}-{}'.format(nows.year, nows.month, nows.day)
    for i in range(1, 4):
        sdk_bg = Image.open(asset('utils', 'sudoku', f'sdk_bg_{i}.png')).convert('RGBA')
        for j in range(81):
            if game_data[i][j].isdigit():
                x1 = 155 + j % 9 * 150
                y1 = 155 + j // 9 * 150
                numj = Image.open(asset('utils', 'sudoku', f'{int(game_data[i][j])}.png')).convert('RGBA')
                sdk_bg.paste(numj, (x1, y1), mask=numj.split()[3])
        draw = ImageDraw.Draw(sdk_bg)
        draw.text(xy=(50, 1560), text=nows, fill=(0, 0, 0), font=font)
        sdk_bg.convert('RGB').save(asset('utils', 'sudoku', f'sdk_diff_{i}.jpg'), format='JPEG', quality=95)

    game_ans = load_game_answers()


async def save_data_backup():
    await save_to_json()
    shutil.copyfile(DATA_FILE, DATA_FILE + '.bak')


timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(reset_daily_challenge, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
async def download_avatar(uid: str) -> bytes:
    url = f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=640"
    datad = await download_url(url)
    if not datad or hashlib.md5(datad).hexdigest() == "acef72340ac0e914090bd35799f5594e":
        url = f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100"
        datad = await download_url(url)
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


def parse_session(ev: MessageEvent):
    """Return (user_id, group_id) from the event's session id."""
    session_id = str(ev.get_session_id())
    if 'group' in session_id:
        parts = session_id.split('_')
        return parts[2], parts[1]
    return session_id, None


async def resting_guard(reply_message: bool = True) -> bool:
    """During rest hours, maybe reply with a notice. Returns True if the
    caller should stop handling the command."""
    notice = await check_anytime()
    if not notice:
        return False
    if random.randint(1, 3) == 1:
        await qiandao.finish(notice, reply_message=reply_message)
    return True


async def ensure_registered(matcher, user_id):
    if user_id not in data:
        await matcher.finish(NOT_REGISTERED_TIP, reply_message=True)


def image_to_base64(img) -> str:
    """Encode a PIL image as a base64 JPEG data URI."""
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return "base64://" + base64.b64encode(buf.getbuffer()).decode()


async def localpath_to_base64(pth):
    with open(pth, "rb") as fil:
        byt = fil.read()
    return "base64://" + base64.b64encode(byt).decode()


async def acquire_jrys(user_id):
    global data
    if not data[user_id]['jrys']:
        data[user_id]['jrys'] = random.randint(1, 80)
    return asset('utils', 'jrys', f'{data[user_id]["jrys"]}.png')


async def get_sticker(x, user_id, mode=1):
    global data, theme_extension
    theme = data[user_id]['theme']
    if theme not in theme_extension:
        theme_extension[theme] = open(asset('stickers', theme, 'extension')).read()
    return asset('stickers', theme, '{}.{}'.format(x, theme_extension[theme]))


async def make_250px(img, mode=0):
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


async def generate_new_sticker(x, user_id, mode=0):
    stk = await get_sticker(x, user_id)
    meme = Image.open(stk).convert('RGBA')
    new_mask = Image.open(asset('utils', 'new.png')).convert('RGBA')
    if mode:
        meme, meme_mask = await make_250px(meme, 1)
    if meme.size[0] / meme.size[1] > new_mask.size[0] / new_mask.size[1]:
        new_mask = new_mask.resize((meme.size[1] // 2 * new_mask.size[0] // new_mask.size[1], meme.size[1] // 2))
    else:
        new_mask = new_mask.resize((meme.size[0] // 2, meme.size[0] // 2 * new_mask.size[1] // new_mask.size[0]))
    meme.paste(new_mask, (0, 0), mask=new_mask.split()[3])
    if mode:
        return meme
    return image_to_base64(meme.convert('RGB'))


def acquire_sticker(user_id, x):  # 1 success, 0 own
    global data
    if x not in data[user_id]['collections']:
        data[user_id]['collections'].append(x)
        return 1
    return 0


async def unlock_segment(user_id, sticker_id, text):
    """Build a 'NEW sticker unlocked' message segment."""
    new_sticker = await generate_new_sticker(sticker_id, user_id)
    return MessageSegment.text(text) + MessageSegment.image(new_sticker)


async def check_all_achiv(user_id, bot: Bot, ev: MessageEvent):
    global data
    if data[user_id]['need_reborn']:
        return
    if any(i not in data[user_id]['collections'] for i in range(1, 101)):
        return
    for j in range(101, 107):
        if j not in data[user_id]['collections']:
            break
    data[user_id]['need_reborn'] = 1
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
    await bot.send(message=MessageSegment.record(asset('utils', 'ngg.wav')), event=ev)


async def check_anytime():
    hour = datetime.datetime.now().hour
    if hour > 21:
        return "慢慢长夜，该睡觉啦～（哈啊）\n祝你做一个美好的梦！\n明天早上6点之后再来找我吧！晚安！"
    elif hour < 6:
        return "Zzz......\n（airi似乎正在睡觉）\n旁边有一张字条：\n熬夜伤身体，请一定要早睡！\n闹钟上的定时：6:00 AM"
    return ""


# --------------------------------------------------------------------------- #
# Command handlers
# --------------------------------------------------------------------------- #
@qiandao.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data, hidden_stickers
    res = '\n'
    user_id, group_id = parse_session(ev)

    once_reg = 0
    if user_id not in data:
        once_reg = 1
        data[user_id] = new_account()
        res += '欢迎来到Airi的收藏世界！\n☑️ 发送指令 签到帮助 查看所有功能哦！\n\n'

    if not data[user_id]['check_times_daily']:
        data[user_id]['checked_days'] += 1
        data[user_id]['check_times_daily'] += 1
        rand_sticker = 17
        while rand_sticker in hidden_stickers:
            rand_sticker = random.randint(1, 100)
        random_credit = 2000 if random.randint(1, 100) == 1 else random.randint(100, 200)
        data[user_id]['credits'] += random_credit
        random_like = 0
        nows = datetime.datetime.now()
        res += '🗓️ {}年{}月{}日 今日已签到！\n'.format(nows.year, nows.month, nows.day)
        res += '🖋️ 已连续签到{}天\n'.format(data[user_id]['checked_days'])
        if random_like:
            res += '获得{}个资料卡点赞\n'.format(random_like)
        msg = MessageSegment.text(res)

        if acquire_sticker(user_id, rand_sticker):
            get_repeat_credit = 0
            new_sticker = await generate_new_sticker(rand_sticker, user_id)
            msg += MessageSegment.text('📦 获得第{}号收藏品\n🎉是NEW，好耶！🎉\n'.format(rand_sticker)) \
                + MessageSegment.image(new_sticker)
        else:
            get_repeat_credit = 50
            data[user_id]['credits'] += 50
            stk = await get_sticker(rand_sticker, user_id)
            stk_b64 = await localpath_to_base64(stk)
            msg += MessageSegment.text('📦 获得第{}号收藏品\n♻️ 重复辣，转化为50积分\n'.format(rand_sticker)) \
                + MessageSegment.image(stk_b64)

        msg += MessageSegment.text(
            '✅ 获得 {} 积分\n📥 当前拥有 {} 积分'.format(random_credit + get_repeat_credit, data[user_id]['credits'])
        )

        random_jrys = random.choice(['💫 来看看今天的运势！', '🔥 我的回合，抽签！', '✨今日运势✨'])
        jrys_img = await acquire_jrys(user_id)
        stk_b64 = await localpath_to_base64(jrys_img)
        msg += MessageSegment.text(f'\n\n{random_jrys}\n') + MessageSegment.image(stk_b64)

        if data[user_id]['credits'] >= 2000 and acquire_sticker(user_id, 20):
            msg += await unlock_segment(
                user_id, 20,
                '\n\n⭐ 隐藏成就解锁！\n🎖️ 积分达到2000：解锁隐藏收藏品20！\n🎉是NEW，好耶！🎉\n',
            )
        if data[user_id]['checked_days'] >= 7 and acquire_sticker(user_id, 100):
            msg += await unlock_segment(
                user_id, 100,
                '\n\n⭐ 隐藏成就解锁！\n🎖️ 连续签到7天：解锁隐藏收藏品100！\n🎉是NEW，好耶！🎉\n',
            )
        if random.randint(1, 100) == 1:
            msg += MessageSegment.text('\n\n' + random.choice(SECRET_MESSAGES))
    else:
        res += '❌ 重复签到{}次！\n'.format(data[user_id]['check_times_daily'])
        data[user_id]['credits'] -= (random_credit := random.randint(10, 20))
        res += '⛔ 已扣除 {} 积分\n📥 当前拥有 {} 积分'.format(random_credit, data[user_id]['credits'])
        msg = MessageSegment.text(res)

        if data[user_id]['check_times_daily'] == 1 and acquire_sticker(user_id, 13):
            msg += await unlock_segment(
                user_id, 13,
                '\n\n⭐ 隐藏成就解锁！\n🎖️ 重复签到1次：解锁隐藏收藏品13！\n🎉是NEW，好耶！🎉\n',
            )
        elif data[user_id]['check_times_daily'] == 5 and acquire_sticker(user_id, 37):
            msg += await unlock_segment(
                user_id, 37,
                '\n\n⭐ 隐藏成就解锁！\n🎖️ 重复签到5次：解锁隐藏收藏品37！\n🎉是NEW，好耶！🎉\n',
            )
        data[user_id]['check_times_daily'] += 1
        if random.randint(1, 100) == 1:
            msg += MessageSegment.text('\n\n' + random.choice(SECRET_MESSAGES))

    await qiandao.send(msg, at_sender=True)
    await check_all_achiv(user_id, bot, ev)


@qiandaohelp.handle()
async def _(bot: Bot, ev: MessageEvent):
    def node(name, content):
        return {"type": "node", "data": {"name": name, "uin": bot.self_id, "content": content}}

    cmd_list = '☑️ 指令列表：\n\
 -签到：字面意思\n\
 -签到帮助：显示该信息\n\
 -收藏信息：查看当前账户信息\n\
 -查看收藏：查看当前收藏集章版\n\
 -查看收藏X（X为数字）：查看编号为X的收藏\n\
 -收藏抽卡：花费100积分抽取一次收藏\n\
 -收藏抽卡X（X为数字）：抽X次\n（重复收藏返还50积分）\n（十连保底出1new）\n\
 -收藏主题：显示所有收藏主题\n\
 -收藏主题xxx：指定当前帐号收藏主题为xxx\n\
 -今日运势：查看你的今日运势！\n\
 -今日挑战：完成游戏获取积分！\n\
 -购买提示：花费500积分购买随机一条有关隐藏收藏品的提示信息\n\n\
（*以下指令需要@机器人*）\n\
 -@Airi 转给@...X个积分（X为数字）：转账给你@的人\n不支持转至未注册账户的人，单日转出限额200积分，手续费10%（向上取整）\n\
 -@Airi 重生：重开存档\n\n\
 （更多功能实装中）'

    gameplay = '☑️ 游戏玩法：\n\
每天签到可以获得积分、资料卡点赞以及随机一个收藏品。\n\
收藏品共计100个，其中95个可以通过抽取获得，其余5个为隐藏收藏品，只有当满足一定条件才可获得。\n\
每集齐一次1-100收藏品即可获得一个创世收藏品。创世收藏品共有五个，重生后再次集齐即可获得第二个，依此类推。\n\
你真能完成全收藏嘛~杂鱼大叔❤'

    custom = '☑️ 收藏主题可以自行定制！\n\
如果你手上有超级多的表情包，且想要为社区做出自己的贡献，不妨将它们发给开发者！\n\
需要素材：100个普通表情包 + 5个创世表情包，一张背景图片。\n准备好后打成压缩包，发送至开发者邮箱saki@saki.ln.cn并备注即可！\n\
如果有更高级的定制需求（集章卡背板，1-100数字蒙版等），可以联系开发者要psd文件！\n你的名字将会出现在你提供的定制主题上。\n\
收藏信息背景也可以自行定制！\n\
将你需要的图片发送至上述邮箱并备注即可！\n\
（支持多张，生成图片时随机挑选）'

    rest_notice = '🔕 每天的22:00-6:00(+1)为休息时间，休息时间内无法使用插件，请合理分配睡眠时间，保持健康作息。'

    msg = [
        node("Momoi Airi Collection", '⚜️ Momoi Airi Collection\n一款签到 + 收藏的娱乐插件'),
        node("指令列表", cmd_list),
        node("游戏玩法", gameplay),
        node("定制说明", custom),
        node("时间限制", rest_notice),
        node("版权信息", 'Powered By AiriCore Dev.'),
    ]
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=msg)


@xinxi.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    await ensure_registered(shoucang, user_id)

    if os.path.exists(asset('info_bg', user_id)):
        bg_list = os.listdir(asset('info_bg', user_id))
        backg = Image.open(asset('info_bg', user_id, random.choice(bg_list))).convert('RGBA')
        xb, yb = backg.size
        backg = backg.resize((1414, 1414 * yb // xb) if yb > xb else (1322 * xb // yb, 1322))
        xb, yb = backg.size
        backg = backg.crop((0, yb // 2 - 661, 1413, yb // 2 + 661) if yb > xb else (xb // 2 - 707, 0, xb // 2 + 707, 1321))
    else:
        backg = Image.open(asset('info_bg', 'default.png')).convert('RGBA')

    overlay_name = 'info_bg_1.png' if data[user_id]['check_times_daily'] else 'info_bg_0.png'
    backg_2 = Image.open(asset('utils', overlay_name)).convert('RGBA')
    backg.paste(backg_2, (0, 0), mask=backg_2.split()[3])

    font_sakura = ImageFont.truetype(font=asset('utils', 'sakura.ttf'), size=36)
    font_louxing = ImageFont.truetype(font=asset('utils', 'louxing.ttf'), size=60)
    font_skc = ImageFont.truetype(font=asset('utils', 'skc.ttf'), size=48)
    draw = ImageDraw.Draw(backg)

    user_nick = ev.sender.card or ev.sender.nickname
    nick_len = draw.textlength(user_nick, font_skc)
    if nick_len > 302:
        user_nick = user_nick[:-1] + "…"
        nick_len = draw.textlength(user_nick, font_skc)
    while nick_len > 302:
        user_nick = user_nick[:-2] + "…"
        nick_len = draw.textlength(user_nick, font_skc)
    draw.text(xy=(92, 264), text=user_nick, fill=(0, 0, 0), font=font_skc)
    draw.text(xy=(92, 337), text='账户ID: ' + user_id, fill=(0, 0, 0), font=font_sakura)

    avater_bytes = await download_avatar(user_id)
    avater = Image.open(BytesIO(avater_bytes)).convert('RGBA').resize((200, 200))
    avater_mask = Image.open(asset('utils', 'avater_mask.png')).convert('RGBA')
    backg.paste(avater, (435, 192), mask=avater_mask.split()[3])

    draw.text(xy=(200 - draw.textlength((tmpdraw := str(data[user_id]["credits"])), font_louxing) // 2, 426), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    draw.text(xy=(520 - draw.textlength((tmpdraw := str(data[user_id]["checked_days"])), font_louxing) // 2, 426), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    draw.text(xy=(900 - draw.textlength((tmpdraw := str(200 - data[user_id]["receive_transfer_daily"])), font_louxing) // 2, 426), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    draw.text(xy=(1220 - draw.textlength((tmpdraw := str(data[user_id]["reborn_times"])), font_louxing) // 2, 426), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    font_louxing = ImageFont.truetype(font=asset('utils', 'louxing.ttf'), size=48)
    draw.text(xy=(1046 - draw.textlength((tmpdraw := str(data[user_id]["theme"])), font_louxing) // 2, 266), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)

    # challenge
    clcp = Image.open(asset('utils', 'complete.png')).convert('RGBA')
    cordx = [0, 792, 988, 1183]
    for i in range(1, 4):
        if data[user_id]["daily_challenge"][i]:
            backg.paste(clcp, (cordx[i], 682), mask=clcp.split()[3])

    # collections
    cl_n = sum(1 for i in range(101) if i in data[user_id]['collections'])
    cl_ur = sum(1 for i in range(101, 106) if i in data[user_id]['collections'])
    font_louxing = ImageFont.truetype(font=asset('utils', 'louxing.ttf'), size=100)
    draw.text(xy=(374 - draw.textlength((tmpdraw := str(cl_n).zfill(3) + '/100'), font_louxing) // 2, 710), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    font_louxing = ImageFont.truetype(font=asset('utils', 'louxing.ttf'), size=120)
    draw.text(xy=(374 - draw.textlength((tmpdraw := str(cl_ur) + '/5'), font_louxing) // 2, 972), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)

    airi_head = Image.open(asset('utils', 'airi.png')).convert('RGBA')
    pgr = Image.new('RGBA', (564, 25), (255 if (rt := (100 - cl_n) * 255 // 50) > 255 else rt, 255 if (gt := cl_n * 255 // 50) > 255 else gt, 0, 0))
    pgr_mask = Image.open(asset('utils', 'pgr_mask.png')).convert('RGBA')
    pgr = pgr.crop((0, 0, 564 * cl_n // 100, 25))
    pgr_mask = pgr_mask.crop((0, 0, 564 * cl_n // 100, 25))
    backg.paste(pgr, (105, 890), mask=pgr_mask.split()[3])
    backg.paste(airi_head, (105 - 37 + 564 * cl_n // 100, 890 - 15), mask=airi_head.split()[3])

    pgr = Image.new('RGBA', (564, 25), (255 if (rt := (50 - cl_ur * 10) * 255 // 25) > 255 else rt, 255 if (gt := cl_n * 2550 // 25) > 255 else gt, 0, 0))
    pgr_mask = Image.open(asset('utils', 'pgr_mask.png')).convert('RGBA')
    pgr = pgr.crop((0, 0, 564 * cl_ur // 5, 25))
    pgr_mask = pgr_mask.crop((0, 0, 564 * cl_ur // 5, 25))
    backg.paste(pgr, (105, 1168), mask=pgr_mask.split()[3])
    backg.paste(airi_head, (105 - 37 + 564 * cl_ur // 5, 1168 - 15), mask=airi_head.split()[3])

    base64_img = image_to_base64(backg.convert('RGB'))
    await xinxi.send(MessageSegment.image(base64_img), reply_message=True)
    del backg, backg_2, font_louxing, font_sakura, font_skc, avater, avater_mask, draw, pgr, pgr_mask
    gc.collect()


@shoucang.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(shoucang, user_id)

    if src == '查看收藏':
        msg = []
        user_nick = ev.sender.card or ev.sender.nickname
        res = '账户昵称：{}\n账户id：{}\n'.format(user_nick, user_id)
        res += '今日已签到！' if data[user_id]['check_times_daily'] else '今日未签到'
        msg.append({"type": "node", "data": {"name": "基本信息", "uin": bot.self_id, "content": res}})

        backg = Image.open(asset('stickers', data[user_id]['theme'], 'bg.png')).convert('RGBA')
        mask = Image.open(asset('stickers', data[user_id]['theme'], 'mask.png')).convert('RGBA')
        unk = Image.open(asset('utils', 'unknown.png')).convert('RGBA')
        unk_mask = unk.split()[3]
        draw = ImageDraw.Draw(backg)
        font = ImageFont.truetype(font=asset('utils', 'font.ttc'), size=48)
        draw.text(xy=(1843, 2783), text=user_nick if len(user_nick) <= 15 else user_nick[:15] + '...', fill=(0, 0, 0), font=font)
        draw.text(xy=(2046, 2841), text=user_id, fill=(0, 0, 0), font=font)
        draw.text(xy=(1816, 2898), text=str(datetime.datetime.now()), fill=(0, 0, 0), font=font)

        own_str = ['', '', '']
        for i in range(1, 101):
            x1 = ((i - 1) % 10) * 250
            y1 = int((i - 1) / 10 + 1) * 250
            if i in data[user_id]['collections']:
                stk = await get_sticker(i, user_id)
                sticker_img, sticker_mask = await make_250px(Image.open(stk).convert('RGBA'))
                backg.paste(sticker_img, (x1, y1), mask=sticker_mask)
            else:
                backg.paste(unk, (x1, y1), mask=unk_mask)
        for i in range(101, 106):
            if i in data[user_id]['collections']:
                stk = await get_sticker(i, user_id)
                sticker_img, sticker_mask = await make_250px(Image.open(stk).convert('RGBA'))
                x1 = ((i - 1) % 10) * 250
                y1 = int((i - 1) / 10 + 1) * 250
                backg.paste(sticker_img, (x1, y1), mask=sticker_mask)
                own_str[2] += '{}, '.format(i)
        own_str[2] = own_str[2][:-2]

        res_img = Image.new('RGBA', backg.size)
        res_img = Image.alpha_composite(res_img, backg)
        res_img = Image.alpha_composite(res_img, mask).convert('RGB')
        base64_img = image_to_base64(res_img)
        await shoucang.send(MessageSegment.image(base64_img), reply_message=True)
        del backg, mask, res_img, base64_img, font, draw
        gc.collect()
    else:
        try:
            query_id = src[4:]
            if query_id[:1] in ["品"]:
                query_id = query_id[1:]
            if query_id[-1:] in ["号"]:
                query_id = query_id[:-1]
            query_id = int(query_id)
            assert query_id in range(1, 106)
        except:
            await shoucang.finish('❌ 请输入正确的收藏编号！', reply_message=True)
        if query_id not in data[user_id]['collections']:
            await shoucang.finish('❌ 你还未拥有该收藏！', reply_message=True)
        stk = await get_sticker(query_id, user_id)
        stk_b64 = await localpath_to_base64(stk)
        msg = MessageSegment.text('📄第{}号收藏\n'.format(query_id)) + MessageSegment.image(stk_b64)
        await shoucang.finish(msg, reply_message=True)


@chouka.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(chouka, user_id)

    if src == '收藏抽卡':
        chouka_times = 1
    else:
        try:
            assert 11 > (chouka_times := int(src[4:])) > 0
        except:
            await chouka.finish('❌ 抽卡次数错误！\n抽卡次数可为：1-10次', reply_message=True)

    if data[user_id]['credits'] < chouka_times * 100:
        await chouka.finish('❌ 积分不够辣！>_<\n需要积分：{}\n现有积分：{}'.format(chouka_times * 100, data[user_id]['credits']), reply_message=True)
    data[user_id]['credits'] -= chouka_times * 100

    tot_new = tot_repeat = 0
    user_nick = ev.sender.card or ev.sender.nickname
    scck_bg_list = os.listdir(asset('utils', 'gacha'))
    backg = Image.open(asset('utils', 'gacha', random.choice(scck_bg_list))).convert('RGBA')
    new_mask = Image.open(asset('utils', 'new_mask.png')).convert('RGBA')
    own_mask = Image.open(asset('utils', 'own_mask.png')).convert('RGBA')
    draw = ImageDraw.Draw(backg)
    font = ImageFont.truetype(font=asset('utils', 'sakura.ttf'), size=56)
    draw.text(xy=(380, 1110), text=user_nick if len(user_nick) <= 15 else user_nick[:15] + '...', fill=(0, 0, 0), font=font)
    draw.text(xy=(540, 1179), text=user_id, fill=(0, 0, 0), font=font)
    draw.text(xy=(351, 1248), text=str(datetime.datetime.now()), fill=(0, 0, 0), font=font)

    new_sticker = pas_sticker = 0
    for i in range(1, chouka_times + 1):
        rand_sticker = 17
        while rand_sticker in hidden_stickers:
            rand_sticker = random.randint(1, 100)
        if i == 10 and tot_repeat == 9:
            nonacq_tmp = [
                j for j in list(set(range(1, 101)) - set(hidden_stickers))
                if j not in data[user_id]['collections']
            ]
            if len(nonacq_tmp):
                rand_sticker = random.choice(nonacq_tmp)

        x1 = (i - 1) % 5 * 375 + 300
        y1 = (i - 1) // 5 * 375 + 300
        if acquire_sticker(user_id, rand_sticker):
            new_sticker = await generate_new_sticker(rand_sticker, user_id, 1)
            backg.paste(new_mask, (x1 - 20, y1 - 20), mask=new_mask.split()[3])
            backg.paste(new_sticker, (x1, y1))
            draw.text(xy=(x1 + 193, y1 - 13), text=f'{rand_sticker}'.zfill(2), fill=(0, 0, 0), font=font)
            draw.text(xy=(x1 + 187, y1 - 19), text=f'{rand_sticker}'.zfill(2), fill=(0, 0, 0), font=font)
            draw.text(xy=(x1 + 190, y1 - 16), text=f'{rand_sticker}'.zfill(2), fill=(255, 0, 0), font=font)
            tot_new += 1
        else:
            data[user_id]['credits'] += 50
            stk = await get_sticker(rand_sticker, user_id)
            pas_sticker, pas_mask = await make_250px(Image.open(stk), 1)
            backg.paste(own_mask, (x1 - 20, y1 - 20), mask=own_mask.split()[3])
            backg.paste(pas_sticker, (x1, y1))
            draw.text(xy=(x1 + 192, y1 - 13), text=f'{rand_sticker}'.zfill(2), fill=(0, 0, 0), font=font)
            draw.text(xy=(x1 + 187, y1 - 19), text=f'{rand_sticker}'.zfill(2), fill=(0, 0, 0), font=font)
            draw.text(xy=(x1 + 190, y1 - 16), text=f'{rand_sticker}'.zfill(2), fill=(255, 255, 0), font=font)
            tot_repeat += 1

    if data[user_id]["need_reborn"]:
        draw.text(xy=(216, 1045), text=f'你已经齐活了，快点重生吧！', fill=(0, 0, 0), font=font)
    elif tot_repeat != 10:
        draw.text(xy=(216, 1045), text=f'重复收藏共转化为{tot_repeat * 50}积分, 剩余积分: {data[user_id]["credits"]}', fill=(0, 0, 0), font=font)
    else:
        draw.text(xy=(216, 1045), text=f'怎么没NEW，是不是有隐藏收藏品……', fill=(0, 0, 0), font=font)

    base64_img = image_to_base64(backg.convert('RGB'))
    await chouka.send(MessageSegment.image(base64_img), reply_message=True)
    await check_all_achiv(user_id, bot, ev)
    del new_sticker, pas_sticker, base64_img, font, draw
    gc.collect()


@yincang17.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    await ensure_registered(yincang17, user_id)

    if acquire_sticker(user_id, 17):
        new_sticker = await generate_new_sticker(17, user_id)
        msg = MessageSegment.text(
            '好小子，怎么让你发现的？\n⭐ 隐藏成就解锁！\n🎖️ 获得第{}号隐藏收藏品\n🎉是NEW，好耶！🎉\n'.format(17)
        ) + MessageSegment.image(new_sticker)
    else:
        msg = MessageSegment.text('😡 拿过了就别再来辣！\nGet out!>_<')
    await yincang17.send(msg, reply_message=True)
    await check_all_achiv(user_id, bot, ev)
    gc.collect()


@transcation.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(transcation, user_id)

    try:
        cq_code = re.findall(r'\[CQ:at,qq=\d+.*\]', src)[0]
        transfer_id = re.findall('\d+', cq_code)[0]
        transfer_num = re.findall(r'[-]?\d+[个]?积分', src)[0]
        transfer_num = transfer_num[:-2] if transfer_num[:-2].isdigit() else transfer_num[:-3]
        transfer_num = int(transfer_num)
        assert transfer_num > 0
    except:
        await transcation.finish('❌ 指令格式不正确！\n单笔转账需在1到50积分之间', reply_message=True)

    if transfer_id not in data:
        await transcation.finish('❌ 收款方未注册账号', reply_message=True)

    taxs = math.ceil(transfer_num * 1.0 / 10)
    if transfer_num + taxs > data[user_id]['credits']:
        await transcation.finish('❌ 你的积分余额不足！\n现有积分：{}\n需要积分(含税)：{}'.format(data[user_id]['credits'], transfer_num + taxs), reply_message=True)
    if transfer_num + data[user_id]['receive_transfer_daily'] > 200:
        await transcation.finish('❌ 已超出今日转出限额！\n账户转出限额：200积分/天\n今日已转出：{}'.format(data[user_id]['receive_transfer_daily']), reply_message=True)

    data[user_id]['receive_transfer_daily'] += transfer_num
    data[user_id]['credits'] -= transfer_num + taxs
    data[transfer_id]['credits'] += transfer_num
    user_nick = await bot.get_group_member_info(group_id=group_id, user_id=transfer_id)
    user_nick = (user_nick.get("nickname") or user_nick.get("card") or transfer_id)
    await transcation.send('✅ 交易成功！\n你已向{}转出了{}积分\nAiri从中收取了{}点手续费(10%)\n剩余积分：{}'.format(user_nick, transfer_num, taxs, data[user_id]['credits']), reply_message=True)

    if data[transfer_id]['credits'] >= 2000 and acquire_sticker(transfer_id, 20):
        new_sticker = await generate_new_sticker(20, transfer_id)
        msg = MessageSegment.at(transfer_id) \
            + MessageSegment.text('\n⭐ 隐藏成就解锁！\n🎖️ 积分达到2000：解锁隐藏收藏品20！\n🎉是NEW，好耶！🎉\n') \
            + MessageSegment.image(new_sticker)
        await transcation.send(msg)
    gc.collect()


@reborn.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(reborn, user_id)

    if src == '重生':
        msg = '\n\
🕗 请仔细阅读以下说明：\n\
 ❌ 以下账户进度会被清空：\n\
  · 积分\n\
  · 1-100号收藏品\n\
 📥 以下账户进度*不会*被清空：\n\
  · 连续签到天数\n\
  · 今日签到情况\n\
  · 今日转账限额\n\
  · 创世收藏品（101-105）\n\
  · 重生次数计数器\n\
 ⚖️ 存在以下情况将无法进行重生操作：\n\
  · 积分 < 0\n\
（友情提醒：只有完成1-100全进度才能累加重生次数）\n\
❗该操作不可逆，请慎重操作❗\n\
🔔 请再次确认你的重生请求，如果确定重生，@我并键入如下内容:\n\
重生（空格）你的QQ号（空格）我已阅读重生说明，请帮我重置账户。\n\
⛔ 存在错字、漏字等情况将不会执行重生操作。'
        await reborn.finish(msg, at_sender=True, reply_message=True)
    elif src == '重生 {} 我已阅读重生说明，请帮我重置账户。'.format(user_id):
        if data[user_id]['credits'] < 0:
            await reborn.finish('😡 捡漏失败：积分<0还想重置账户？爬爬爬！', reply_message=True)
        await check_all_achiv(user_id, bot, ev)
        data[user_id]['credits'] = 0
        data[user_id]['collections'] = [i for i in range(101, 106) if i in data[user_id]['collections']]
        if data[user_id]['need_reborn']:
            data[user_id]['need_reborn'] = 0
            data[user_id]['reborn_times'] += 1
        await reborn.send('\n✅ 重生操作已成功完成！', at_sender=True, reply_message=True)
    else:
        await reborn.finish('\n❌ 请求不正确！请检查是否存在错字、漏字等情况。', at_sender=True, reply_message=True)


@theme_manage.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(theme_manage, user_id)

    theme_list = sorted(os.listdir(asset('stickers')))
    if src == '收藏主题':
        res = '⭐ 当前收藏主题：{}\n\n🗒️ 所有主题：'.format(data[user_id]['theme'])
        for i in range(len(theme_list)):
            res += '\n{}. {}'.format(i + 1, theme_list[i])
        await theme_manage.finish(res, reply_message=True)
    else:
        change_theme = src[4:].lstrip()
        if change_theme.isdigit() and int(change_theme) <= len(theme_list):
            change_theme = theme_list[int(change_theme) - 1]
        if change_theme not in theme_list:
            await theme_manage.finish('❌ 找不到该主题，请检查拼写！', reply_message=True)
        data[user_id]['theme'] = change_theme
        await theme_manage.send('✅ 主题更改成功！\n当前收藏主题：{}'.format(data[user_id]['theme']), reply_message=True)


@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    global data
    user_id, group_id = parse_session(ev)
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  ", " ")) != src:
        src = tmpa

    user_2fa_digit = src[:6]
    if not totp_verify(_2fa_key, user_2fa_digit):
        await superuser_debug.finish('2fa verification failed')
    src = src[6:].strip()

    user_nick = ev.sender.card or ev.sender.nickname
    if src == 'reset':
        await daily_clear()
        res = '刷新一天：命令执行成功'
    elif src == 'save':
        await save_to_json()
        res = '存档：命令执行成功'
    elif src == 'backup':
        await save_data_backup()
        res = '备份：命令执行成功'
    elif src == 'load':
        await load_json()
        res = '读档：命令执行成功'
    elif src == 'rdc':
        await reset_daily_challenge()
        res = '重置每日挑战：命令执行成功'
    else:
        try:
            try:
                res = eval(src)
            except:
                res = exec(src)
        except Exception as err:
            res = '出错了: ' + repr(err)
        else:
            res = '命令执行成功' if not res else str(res)
    await superuser_debug.finish(res, reply_message=True)


@daily_challenge.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard(reply_message=False):
        return
    nows = datetime.datetime.now()
    res = MessageSegment.text('㊙️ 快来挑战今日份数独题目吧！\n{}年{}月{}日\n'.format(nows.year, nows.month, nows.day))
    for i in range(1, 4):
        stk = asset('utils', 'sudoku', f'sdk_diff_{i}.jpg')
        stk_b64 = await localpath_to_base64(stk)
        res += MessageSegment.text(f'\n{DIFFICULTY[i]}难度 - {CREDIT_BY_DIFF[i]}积分')
        res += MessageSegment.image(stk_b64)
    res += MessageSegment.text('\n\n📬 如何提交：\n请访问 https://www.airi.asia/posts/mac_flag_generator/ 并按照网页指示进行操作。')
    await daily_challenge.finish(res, reply_message=True)


@flag_submit.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data, game_ans
    user_id, group_id = parse_session(ev)
    src = str(ev.message).strip()[5:-1]
    await ensure_registered(flag_submit, user_id)

    for i in range(1, 4):
        hash_res = hmac.new(user_id.encode(), game_ans[i].encode(), hashlib.md5).hexdigest()
        if src == hash_res:
            if not data[user_id]['daily_challenge'][i]:
                data[user_id]['credits'] += CREDIT_BY_DIFF[i]
                data[user_id]['daily_challenge'][i] = 1
                msg = MessageSegment.text(
                    f'\n✅ 提交成功！\n恭喜你解出了每日挑战{DIFFICULTY[i]}难度，获得{CREDIT_BY_DIFF[i]}积分奖励！\n当前积分：{data[user_id]["credits"]}'
                )
                if data[user_id]['credits'] >= 2000 and acquire_sticker(user_id, 20):
                    msg += await unlock_segment(
                        user_id, 20,
                        '\n\n⭐ 隐藏成就解锁！\n🎖️ 积分达到2000：解锁隐藏收藏品20！\n🎉是NEW，好耶！🎉\n',
                    )
                await flag_submit.finish(msg, at_sender=True, reply_message=True)
            else:
                await flag_submit.finish(f'❌ 今日已完成{DIFFICULTY[i]}难度，请勿重复提交！', reply_message=True)
    await flag_submit.finish('⛔ 你提交的Flag好像不是很对哦', reply_message=True)


@buy_tip.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    await ensure_registered(buy_tip, user_id)

    if data[user_id]['credits'] < 500:
        await buy_tip.finish('😡 500积分都拿不出来的吗！', reply_message=True)
    else:
        data[user_id]['credits'] -= 500
        await buy_tip.finish(
            f'{random.choice(SECRET_MESSAGES)}\n\n剩余积分：{data[user_id]["credits"]}',
            reply_message=True,
        )


@jrys.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    global data
    user_id, group_id = parse_session(ev)
    await ensure_registered(jrys, user_id)

    jrys_img = await acquire_jrys(user_id)
    stk_b64 = await localpath_to_base64(jrys_img)
    await jrys.finish(MessageSegment.text('\n✨今日运势✨\n') + MessageSegment.image(stk_b64), at_sender=True)
    
_roguelike = importlib.import_module(
    f"{__package__}.roguelike" if __package__ else "roguelike"
)
