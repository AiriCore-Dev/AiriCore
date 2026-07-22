import os
import re
import io
import sys
import json
import base64
import mcrcon
import random
import psutil
import nbtlib
import shutil
import pickle
import aiohttp
import asyncio
import nonebot
import hashlib
import requests
import traceback
from utils.totp_2fa import totp_verify
from mcrcon import MCRcon
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot import get_driver, on_startswith, require
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

driver = get_driver()
rcon_password = getattr(driver.config, "rcon_password", "")
_2fa_key = getattr(driver.config, "_2fa_key", "")
timing = require("nonebot_plugin_apscheduler").scheduler
data = {}
mcr = MCRcon("127.0.0.1", rcon_password)
server_path = '/root/airi/airicob5'

bote = 0
op_list = ["864623174"]
whitelist_group_list = ["740774974", "466470972"]

BASE_DIR = os.path.dirname(__file__)
FONT_PATH = os.path.join(BASE_DIR, "utils", "font.ttf")



def parse_session(ev):
    session_id = str(ev.get_session_id())
    if 'group' in session_id:
        _, group_id, user_id = session_id.split("_")
        return user_id, group_id
    return session_id, None


def require_account(uid, msg="你还未绑定游戏账户"):
    if uid not in data:
        raise ValueError(msg)
    return data[uid]


def parse_at_qq(raw, usage):
    if not (raw.startswith('[CQ:at,qq=') and raw.endswith(']')):
        raise ValueError(usage)
    qq = raw[10:-1].strip()
    try:
        int(qq)
    except Exception:
        raise ValueError(usage)
    return qq



async def generate_minecraft_head(username):
    uuid_url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(uuid_url) as response:
                response.raise_for_status()
                uuid = (await response.json())["id"]

            head_url = f"https://minotar.net/avatar/{uuid}"
            async with session.get(head_url) as head_response:
                head_response.raise_for_status()
                head_image = await head_response.read()

        return Image.open(io.BytesIO(head_image)).resize((120, 120)).convert('RGBA')
    except Exception:
        return None


async def create_pokemon_card(pokemon_list):
    AVATAR_DIR = os.path.join(BASE_DIR, "poke_avater")
    GENDER_DIR = os.path.join(BASE_DIR, "utils")
    ITEM_DIR = os.path.join(BASE_DIR, "item")

    def create_blank(size=(320, 320)):
        return Image.new("RGBA", size, (0, 0, 0, 200))

    def process_pokemon(pokemon):
        avatar = create_blank()

        avatar_path = os.path.join(AVATAR_DIR, f"{pokemon['name']}.png")
        if os.path.exists(avatar_path):
            tmp = Image.open(avatar_path).convert("RGBA")
            avatar.paste(tmp, (0, 0), tmp)

        if pokemon.get('gender') in ['male', 'female']:
            gender_img = Image.open(os.path.join(GENDER_DIR, f"{pokemon['gender']}.png")).convert("RGBA")
            avatar.paste(gender_img, (10, 10), gender_img)

        draw = ImageDraw.Draw(avatar)
        try:
            level_text = f"lvl.{pokemon['level']}"
            font = ImageFont.truetype(FONT_PATH, 36)
            for dx, dy in [(-1, -1), (1, 1), (1, -1), (-1, 1)]:
                draw.text((10 + dx, 270 + dy), level_text, font=font, fill="black")
            draw.text((10, 270), level_text, font=font, fill="white")
        except Exception as e:
            print(f"字体加载失败: {e}")

        if pokemon.get('item') and pokemon['item'] != 'None':
            item_path = os.path.join(ITEM_DIR, f"{pokemon['item']}.png")
            if os.path.exists(item_path):
                item_img = Image.open(item_path).convert("RGBA")
                avatar.paste(item_img, (320 - 48 - 10, 320 - 50), item_img)

        if pokemon.get('shiny', False):
            shiny_img = Image.open(os.path.join(GENDER_DIR, "shiny.png")).convert("RGBA")
            avatar.paste(shiny_img, (320 - 48 - 10, 5), shiny_img)

        return avatar

    cards = [process_pokemon(p) for p in pokemon_list]

    cols, rows = 2, 3
    card_size, spacing, diverseY = 320, 50, 125
    total_width = cols * card_size + (cols - 1) * spacing
    total_height = rows * card_size + (rows - 1) * spacing + diverseY

    big_image = Image.new("RGBA", (total_width, total_height), (255, 255, 255, 0))
    for idx, card in enumerate(cards):
        x = (idx % cols) * (card_size + spacing)
        y = (idx // cols) * (card_size + spacing) + (diverseY if idx % 2 else 0)
        big_image.paste(card, (x, y), card)

    return big_image


async def extract_pokemon_player_data(nbt_file_path):
    try:
        pokemon_player_data = dict(nbtlib.load(nbt_file_path))
    except FileNotFoundError:
        return []

    slot_count = pokemon_player_data.get('SlotCount', 0)
    pokemon_list = []

    for i in range(slot_count):
        pokemon = pokemon_player_data.get(f'Slot{i}')
        if pokemon is None:
            continue

        held = pokemon.get('HeldItem')
        held_item = held['id'].split(':')[-1] if held and 'id' in held else 'None'

        pokemon_list.append({
            'name': pokemon['Species'].split(':')[-1],
            'level': int(pokemon['Level']),
            'gender': str(pokemon['Gender']).lower(),
            'item': held_item,
            'shiny': pokemon['Shiny'] == 1,
        })

    return pokemon_list


async def create_bag_image_with_elements(img1, img2, player_name):
    background = Image.new('RGB', (800, 1440), color='#444444')
    try:
        background.paste(img1, (35, 35), img1)
    except Exception:
        pass
    background.paste(img2, (55, 200), img2)
    draw = ImageDraw.Draw(background)
    font = ImageFont.truetype(FONT_PATH, 60)
    draw.text((200, 62), player_name, font=font, fill=(255, 255, 255))
    return background


async def generate_pokemon_bag(player_name):
    player_uuid = ""
    with open(os.path.join(server_path, "usercache.json"), 'r') as f:
        for entry in json.load(f):
            if entry['name'] == player_name:
                player_uuid = entry['uuid']
                break

    nbt_file_path = os.path.join(
        server_path, 'world', 'pokemon', 'playerpartystore',
        player_uuid[:2], f'{player_uuid}.dat'
    )
    pokemon_list = await extract_pokemon_player_data(nbt_file_path)
    pokemon_card = await create_pokemon_card(pokemon_list)
    player_avatar = await generate_minecraft_head(player_name)
    res = await create_bag_image_with_elements(player_avatar, pokemon_card, player_name)

    byt = io.BytesIO()
    res.save(byt, format="PNG")
    return 'base64://' + base64.b64encode(byt.getvalue()).decode()



async def load_json():
    global data
    try:
        with open(os.path.join('data', 'airi_mcrcon', 'data.pk'), 'rb') as f:
            data = pickle.load(f)
    except Exception:
        os.makedirs(os.path.join('data', 'airi_mcrcon'), exist_ok=True)
        await save_json()


async def save_json():
    with open(os.path.join('data', 'airi_mcrcon', 'data.pk'), 'wb') as f:
        pickle.dump(data, f)



async def check_alive():
    global mcr
    try:
        mcr.command('execute as QHSISQ_NOBODY run seed')
    except Exception:
        try:
            mcr.disconnect()
            mcr = MCRcon("127.0.0.1", rcon_password)
            mcr.connect()
        except Exception:
            pass


async def clear_item():
    global mcr, bote
    try:
        mcr.command('say 即将在30s后清理掉落物')
        await asyncio.sleep(25)
        for i in range(5, 0, -1):
            mcr.command(f'say 掉落物清理倒计时：{i}')
            await asyncio.sleep(1)
        msg = mcr.command('kill @e[type=item]')
        mcr.command(f'say 已清理{msg.split()[1]}个掉落物')

        ctemp = psutil.sensors_temperatures()["coretemp"][0].current
        if ctemp > 84.9:
            await bote.send_group_msg(
                group_id=740774974,
                message=f"警告：服务器CPU温度过高！\n{ctemp} ℃\n请适当降低跑图频率，如果有高频红石或者科技正在运行也请歇一歇，公益开服，还请大家共同努力，维护服务器健康，谢谢大家！"
            )
        return "执行成功"
    except Exception as err:
        return "出错了：" + str(err)


timing.add_job(clear_item, "cron", minute=30, misfire_grace_time=3600, coalesce=True)


async def format_duration(seconds):
    if seconds <= 0:
        return "0秒"
    units = [('天', 86400), ('小时', 3600), ('分钟', 60), ('秒', 1)]
    parts = []
    remaining = seconds
    for unit_name, unit_seconds in units:
        if remaining >= unit_seconds:
            parts.append(f"{remaining // unit_seconds}{unit_name}")
            remaining %= unit_seconds
            if remaining == 0:
                break
    return ''.join(parts)


async def timestamp_to_datetime(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")



@driver.on_startup
async def _():
    try:
        await load_json()
        mcr.connect()
    except Exception:
        pass


@driver.on_shutdown
async def _():
    try:
        mcr.disconnect()
    except Exception:
        pass



HELP_TEXT = '''支持的指令：
/connect ：连接指令服务器
/help ：查看这条信息
/auth 你的mc玩家名 ：绑定账号
（进入服务器前必须）
/unauth ：解绑
/seed ：查看地图种子
/list ：查看在线玩家
/banlist ：查看封神榜
/tpa @群友 ：将自己传送到你@群友的位置
/locate ：定位结构
/playerspawn ：站立不动三秒后将自己传送回出生点（中途移动中断）
/pokebag ：查看自己背包内的宝可梦
/pokebag @群友 ：查看群友背包内的宝可梦'''

rcon_handle = on_startswith('/', priority=10)
superuser_debug = on_startswith('mdebug ', priority=5, block=True, rule=to_me(), permission=SUPERUSER)


@rcon_handle.handle()
async def _(bot: Bot, ev: MessageEvent):
    global data, bote
    user_id, gruop_id = parse_session(ev)
    if gruop_id not in whitelist_group_list:
        return
    bote = bot

    src = str(ev.message)[1:].strip().replace('&#91;', '[').replace('&#93;', ']')
    is_op = user_id in op_list

    if src == 'connect':
        try:
            mcr.connect()
            res = 'RCON已连接'
        except Exception as err:
            res = f"连接出错：{str(err)}"
        await rcon_handle.finish(res.strip())
    elif is_op and src == 'disconnect':
        try:
            mcr.disconnect()
            res = 'RCON已下线'
        except Exception as err:
            res = f"出错了：{str(err)}"
        await rcon_handle.finish(res.strip())
    elif src == "help":
        await rcon_handle.finish(HELP_TEXT.strip())

    await check_alive()

    if src.startswith('auth'):
        try:
            name = src[4:].strip()
            if not name:
                raise ValueError("指令用法：/auth 你的mc玩家名")
            if name in list(data.values()):
                raise ValueError("该游戏账户已被其他QQ号绑定")
            if user_id not in data:
                data[user_id] = {}
            else:
                mcr.command(f'easywhitelist remove {data[user_id]["username"]}')
                mcr.command(f'auth remove {data[user_id]["username"]}')
            rand_passwd = hashlib.md5(str(random.random()).encode()).hexdigest()
            data[user_id]["username"] = name
            data[user_id]["password"] = rand_passwd
            mcr.command(f'easywhitelist add {name}')
            mcr.command(f'auth register {name} {rand_passwd}')
            await save_json()
            res = '认证成功！\n你现在可以进入服务器了'
        except Exception as err:
            res = f"{str(err)}"
    elif src == 'unauth':
        try:
            username = require_account(user_id)["username"]
            mcr.command(f'easywhitelist remove {username}')
            mcr.command(f'auth remove {username}')
            del data[user_id]
            await save_json()
            res = '注销成功'
        except Exception as err:
            res = f"{str(err)}"
    elif src == 'login':
        try:
            account = require_account(user_id)
            mcr.command(f'execute as {account["username"]} run login {account["password"]}')
            res = '登录成功'
        except Exception as err:
            res = f"{str(err)}"
    elif src == 'banlist':
        try:
            mcr.command("banhammer export_all_punishments")
            file_path = os.path.join(server_path, "banhammer_exports.json")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    datab = json.load(f)
                ban_records = datab.get('active', [])
                if not len(ban_records):
                    raise ValueError("当前封神榜为空")
                output_lines = []
                for record in ban_records:
                    player_name = record.get('playerName', '未知玩家')
                    reason = record.get('reason', '无原因')
                    ban_time = record.get('time', 0)
                    duration = record.get('duration', 0)
                    unban_time = ban_time + duration
                    ban_time_str = await timestamp_to_datetime(ban_time)
                    duration_str = await format_duration(duration) if duration + 1 else "永久封禁"
                    unban_time_str = await timestamp_to_datetime(unban_time) if duration + 1 else "-"
                    output_lines.extend([
                        f"玩家名：{player_name[0]}***{player_name[-1]}",
                        f"被封禁原因：{reason}",
                        f"决定时间：{ban_time_str}",
                        f"被封禁时长：{duration_str}",
                        f"解除于：{unban_time_str}",
                        ""
                    ])
                res = '\n'.join(output_lines[:-1]).strip()
            except FileNotFoundError:
                raise ValueError(f"错误：找不到文件 {file_path}")
            except json.JSONDecodeError:
                raise ValueError("错误：JSON文件格式无效")
            except Exception as e:
                raise ValueError(f"{str(e)}")
        except Exception as err:
            res = f"{str(err)}"
    elif src in ["list", "seed"]:
        try:
            res = mcr.command(src)
        except Exception as err:
            res = f"{str(err)}"
    elif src == "playerspawn":
        try:
            username = require_account(user_id)["username"]
            res = mcr.command(f'execute at {username} run {src}')
        except Exception as err:
            res = f"{str(err)}"
    elif src.startswith('pokebag'):
        try:
            target = src[7:].strip()
            if not target:
                target = user_id
            else:
                target = parse_at_qq(target, "指令用法：/pokebag 或 /pokebag @群友")
            username = require_account(target, "指定的用户未绑定游戏账户")["username"]
            res = await generate_pokemon_bag(username)
            await rcon_handle.send(MessageSegment.image(res), reply_message=True)
            return
        except Exception as err:
            res = f"{str(err)}"
    elif src.startswith('tpa'):
        try:
            from_user = require_account(user_id)["username"]
            target = parse_at_qq(src[3:].strip(), "指令用法：/tpa @群友")
            to_user = require_account(target, "对方未绑定游戏账户")["username"]
            res = mcr.command(f'tp {from_user} {to_user}')
        except Exception as err:
            res = f"{str(err)}"
    elif src.startswith('locate'):
        try:
            username = require_account(user_id)["username"]
            res = mcr.command(f'execute at {username} run {src}')
        except Exception as err:
            res = f"{str(err)}"
    elif is_op and src == "clearitem":
        try:
            res = await clear_item()
        except Exception as err:
            res = f"{str(err)}"
    elif is_op:
        try:
            src = re.sub(r'\[CQ:at,\s*qq=(\d+)\]', lambda x: data[x.group(1)]["username"], src)
            res = mcr.command(src)
        except Exception as err:
            res = f"{str(err)}"
    else:
        res = "你没有权限执行该指令"

    await rcon_handle.finish(res.rstrip() if len(res) else "执行成功（输出为空）", reply_message=True)


@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    global data
    user_id, gruop_id = parse_session(ev)

    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  ", " ")) != src:
        src = tmpa

    if not totp_verify(_2fa_key, src[:6]):
        await superuser_debug.finish('2fa verification failed')
    src = src[6:].strip()
    user_nick = ev.sender.card or ev.sender.nickname

    is_await = src[:6] == 'await '
    expr = src[6:].lstrip() if is_await else src
    try:
        try:
            res = await eval(expr) if is_await else eval(expr)
        except Exception:
            res = await exec(expr) if is_await else exec(expr)
        res = '命令执行成功' if not res else str(res)
    except Exception:
        res = traceback.format_exc()

    await superuser_debug.finish(res, reply_message=True)
