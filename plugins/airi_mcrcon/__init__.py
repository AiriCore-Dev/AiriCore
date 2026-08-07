import os
import re
import io
import json
import base64
import random
import psutil
import nbtlib
import pickle
import aiohttp
import asyncio
import nonebot
import hashlib
import tempfile
import traceback
from pathlib import Path
from utils.totp_2fa import totp_verify
from .rcon_safe import SafeMCRcon, get_executor, shutdown_executor
from openai import AsyncOpenAI
from datetime import datetime
from PIL import Image, ImageDraw
from utils import cache as asset_cache
from utils import llm_fallback
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot import get_driver, logger, on_startswith, require
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent

driver = get_driver()
rcon_password = getattr(driver.config, "rcon_password", "")
rcon_host = str(getattr(driver.config, "rcon_host", "") or "127.0.0.1")
rcon_port = int(getattr(driver.config, "rcon_port", 0) or 25575)
RCON_TIMEOUT = 8
_2fa_key = str(getattr(driver.config, "_2fa_key", "") or "").strip()
llm_api_key = getattr(driver.config, "llm_api_key", "")
llm_base_url = getattr(driver.config, "llm_base_url", "")
timing = require("nonebot_plugin_apscheduler").scheduler
data = {}
translate_groups = {}
mcr = SafeMCRcon(rcon_host, rcon_password, port=rcon_port, timeout=RCON_TIMEOUT)
_rcon_lock = asyncio.Lock()
_account_tx_lock = asyncio.Lock()
server_path = str(getattr(driver.config, "mc_server_path", "") or '/root/airi/airicob5')

MC_NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "airi_mcrcon"


def _sync_command(cmd: str) -> str:
    return mcr.command(cmd)


async def _run_rcon(fn, *args, timeout: float = None):
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(get_executor(), fn, *args)
    try:
        return await asyncio.wait_for(
            asyncio.shield(fut), timeout=RCON_TIMEOUT + 4 if timeout is None else timeout
        )
    except (asyncio.TimeoutError, asyncio.CancelledError):
        mcr.force_close()
        fut.add_done_callback(lambda f: f.exception())
        raise


async def rcon(cmd: str) -> str:
    async with _rcon_lock:
        return await _run_rcon(_sync_command, cmd)


def require_mc_name(name: str) -> str:
    name = (name or "").strip()
    if not MC_NAME_RE.match(name):
        raise ValueError("玩家名不合法，只允许 3-16 位字母、数字和下划线")
    return name

llm_client = AsyncOpenAI(api_key=llm_api_key, base_url=llm_base_url)

TRANSLATE_PROMPT = '''你是一个 Minecraft 服务器控制台输出的翻译助手。请将用户给出的服务器原始输出翻译成自然流畅的简体中文。要求：
1. 只输出翻译结果，不要添加任何解释、前缀或额外说明；
2. 保留玩家名、坐标、维度 id、命令名等专有名词与数字原样；
3. 已经是中文的内容原样保留；
4. 保持原有的换行与分行结构。'''


async def translate_to_chinese(text):
    if not text or not text.strip():
        return text
    try:
        return await llm_fallback.call_with_fallback(
            llm_client,
            [
                {"role": "system", "content": TRANSLATE_PROMPT},
                {"role": "user", "content": text},
            ],
            tag="mcrcon_translate",
            temperature=0.2,
            stream=False,
            stop=None,
        )
    except Exception:
        return text

def _cfg_list(key, default):
    raw = getattr(driver.config, key, None)
    if raw is None:
        return list(default)
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return [str(x).strip() for x in raw if str(x).strip()]


whitelist_group_list = _cfg_list("mc_whitelist_groups", ["740774974", "466470972", "1075068454"])
alert_group_id = str(getattr(driver.config, "mc_alert_group", "") or (whitelist_group_list[0] if whitelist_group_list else ""))

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
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
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


def _create_pokemon_card_sync(pokemon_list):
    AVATAR_DIR = os.path.join(BASE_DIR, "poke_avater")
    GENDER_DIR = os.path.join(BASE_DIR, "utils")
    ITEM_DIR = os.path.join(BASE_DIR, "item")

    def create_blank(size=(320, 320)):
        return Image.new("RGBA", size, (0, 0, 0, 200))

    def process_pokemon(pokemon):
        avatar = create_blank()

        avatar_path = os.path.join(AVATAR_DIR, f"{pokemon['name']}.png")
        if os.path.exists(avatar_path):
            tmp = asset_cache.get_image(avatar_path)
            avatar.paste(tmp, (0, 0), tmp)

        if pokemon.get('gender') in ['male', 'female']:
            gender_img = asset_cache.get_image(os.path.join(GENDER_DIR, f"{pokemon['gender']}.png"))
            avatar.paste(gender_img, (10, 10), gender_img)

        draw = ImageDraw.Draw(avatar)
        try:
            level_text = f"lvl.{pokemon['level']}"
            font = asset_cache.get_font(FONT_PATH, 36)
            for dx, dy in [(-1, -1), (1, 1), (1, -1), (-1, 1)]:
                draw.text((10 + dx, 270 + dy), level_text, font=font, fill="black")
            draw.text((10, 270), level_text, font=font, fill="white")
        except Exception as e:
            logger.warning(f"airi_mcrcon 字体加载失败: {e}")

        if pokemon.get('item') and pokemon['item'] != 'None':
            item_path = os.path.join(ITEM_DIR, f"{pokemon['item']}.png")
            if os.path.exists(item_path):
                item_img = asset_cache.get_image(item_path)
                avatar.paste(item_img, (320 - 48 - 10, 320 - 50), item_img)

        if pokemon.get('shiny', False):
            shiny_img = asset_cache.get_image(os.path.join(GENDER_DIR, "shiny.png"))
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


def _extract_pokemon_sync(nbt_file_path):
    try:
        pokemon_player_data = dict(nbtlib.load(nbt_file_path))
    except (FileNotFoundError, IsADirectoryError, OSError):
        return []
    except Exception as e:
        logger.warning(f"airi_mcrcon 背包 NBT 解析失败: {e}")
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


def _create_bag_image_sync(img1, img2, player_name):
    background = Image.new('RGB', (800, 1440), color='#444444')
    try:
        background.paste(img1, (35, 35), img1)
    except Exception:
        pass
    background.paste(img2, (55, 200), img2)
    draw = ImageDraw.Draw(background)
    font = asset_cache.get_font(FONT_PATH, 60)
    draw.text((200, 62), player_name, font=font, fill=(255, 255, 255))
    return background


_usercache: dict = {}
_usercache_sig = None


def _load_usercache_sync():
    global _usercache, _usercache_sig
    path = os.path.join(server_path, "usercache.json")
    try:
        st = os.stat(path)
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        return {}
    if sig == _usercache_sig and _usercache:
        return _usercache
    try:
        with open(path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        _usercache = {
            str(e.get('name', '')): str(e.get('uuid', ''))
            for e in entries if e.get('name') and e.get('uuid')
        }
        _usercache_sig = sig
    except Exception as e:
        logger.warning(f"airi_mcrcon usercache 解析失败: {e}")
        return _usercache
    return _usercache


async def lookup_player_uuid(player_name: str) -> str:
    cache = await asyncio.to_thread(_load_usercache_sync)
    return cache.get(player_name, "")


def _render_bag_sync(pokemon_list, player_avatar, player_name):
    pokemon_card = _create_pokemon_card_sync(pokemon_list)
    res = _create_bag_image_sync(player_avatar, pokemon_card, player_name)
    byt = io.BytesIO()
    res.save(byt, format="PNG")
    return 'base64://' + base64.b64encode(byt.getvalue()).decode()


async def generate_pokemon_bag(player_name):
    player_name = require_mc_name(player_name)
    player_uuid = await lookup_player_uuid(player_name)
    if not player_uuid:
        raise ValueError("该玩家还没有进过服务器，暂时查不到背包")

    nbt_file_path = os.path.join(
        server_path, 'world', 'pokemon', 'playerpartystore',
        player_uuid[:2], f'{player_uuid}.dat'
    )
    pokemon_list = await asyncio.to_thread(_extract_pokemon_sync, nbt_file_path)
    player_avatar = await generate_minecraft_head(player_name)
    return await asyncio.to_thread(_render_bag_sync, pokemon_list, player_avatar, player_name)



def _atomic_dump(path: Path, obj) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(_DATA_DIR), prefix=".tmp-", suffix=".pk")
    try:
        with os.fdopen(fd, "wb") as f:
            pickle.dump(obj, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_pickle(path: Path, label: str):
    if not path.is_file():
        return {}, False
    try:
        with open(path, 'rb') as f:
            loaded = pickle.load(f)
        if not isinstance(loaded, dict):
            raise ValueError("数据结构异常")
        return loaded, False
    except Exception as e:
        bak = path.with_suffix(path.suffix + ".corrupt")
        try:
            os.replace(path, bak)
        except OSError:
            pass
        logger.error(f"airi_mcrcon {label} 读取失败，已保留坏档到 {bak.name}，不会覆盖: {e}")
        return {}, True


async def load_json():
    global data
    loaded, broken = _load_pickle(_DATA_DIR / 'data.pk', '绑定数据')
    data = loaded
    if not broken and not (_DATA_DIR / 'data.pk').is_file():
        await save_json()


async def save_json():
    _atomic_dump(_DATA_DIR / 'data.pk', data)


async def load_translate():
    global translate_groups
    loaded, broken = _load_pickle(_DATA_DIR / 'translate.pk', '翻译开关')
    translate_groups = loaded
    if not broken and not (_DATA_DIR / 'translate.pk').is_file():
        await save_translate()


async def save_translate():
    _atomic_dump(_DATA_DIR / 'translate.pk', translate_groups)


async def _rcon_rollback(cmd: str) -> None:
    try:
        await rcon(cmd)
    except Exception as e:
        logger.warning(f"airi_mcrcon 绑定回滚指令失败 {cmd!r}: {e}")


async def _bind_account(user_id: str, name: str) -> None:
    async with _account_tx_lock:
        owners = [
            qq for qq, value in data.items()
            if isinstance(value, dict)
            and str(value.get("username", "")).lower() == name.lower()
        ]
        if [qq for qq in owners if qq != user_id]:
            raise ValueError("该游戏账户已被其他QQ号绑定")
        old_account = dict(data[user_id]) if user_id in data else None
        old_name = require_mc_name(old_account["username"]) if old_account else None
        old_password = old_account.get("password", "") if old_account else ""
        password = hashlib.md5(str(random.random()).encode()).hexdigest()
        same_name = old_name is not None and old_name.lower() == name.lower()
        new_whitelist_attempted = False
        new_register_attempted = False
        restore_old = False
        committed = False
        try:
            if same_name:
                restore_old = True
                await rcon(f'easywhitelist remove {old_name}')
                await rcon(f'auth remove {old_name}')

            new_whitelist_attempted = True
            await rcon(f'easywhitelist add {name}')
            new_register_attempted = True
            await rcon(f'auth register {name} {password}')

            if old_name and not same_name:
                restore_old = True
                await rcon(f'easywhitelist remove {old_name}')
                await rcon(f'auth remove {old_name}')

            data[user_id] = {"username": name, "password": password}
            try:
                await save_json()
            except Exception:
                if old_account is None:
                    data.pop(user_id, None)
                else:
                    data[user_id] = old_account
                raise
            committed = True
        finally:
            if not committed:
                if new_register_attempted:
                    await _rcon_rollback(f'auth remove {name}')
                if new_whitelist_attempted:
                    await _rcon_rollback(f'easywhitelist remove {name}')
                if restore_old and old_name:
                    await _rcon_rollback(f'easywhitelist add {old_name}')
                    await _rcon_rollback(
                        f'auth register {old_name} {old_password}'
                    )


async def _unbind_account(user_id: str) -> None:
    async with _account_tx_lock:
        old_account = dict(require_account(user_id))
        username = require_mc_name(old_account["username"])
        password = old_account.get("password", "")
        whitelist_remove_attempted = False
        auth_remove_attempted = False
        committed = False
        try:
            whitelist_remove_attempted = True
            await rcon(f'easywhitelist remove {username}')
            auth_remove_attempted = True
            await rcon(f'auth remove {username}')
            data.pop(user_id, None)
            try:
                await save_json()
            except Exception:
                data[user_id] = old_account
                raise
            committed = True
        finally:
            if not committed:
                if whitelist_remove_attempted:
                    await _rcon_rollback(f'easywhitelist add {username}')
                if auth_remove_attempted:
                    await _rcon_rollback(
                        f'auth register {username} {password}'
                    )


def _sync_reconnect() -> None:
    mcr.force_close()
    mcr.connect()


async def check_alive():
    try:
        await rcon('execute as QHSISQ_NOBODY run seed')
        return True
    except Exception:
        pass
    try:
        async with _rcon_lock:
            await _run_rcon(_sync_reconnect)
        return True
    except Exception as e:
        logger.warning(f"airi_mcrcon RCON 重连失败: {e}")
        return False


def read_cpu_temp():
    getter = getattr(psutil, "sensors_temperatures", None)
    if getter is None:
        return None
    try:
        temps = getter() or {}
    except Exception:
        return None
    for key in ("coretemp", "k10temp", "cpu_thermal", "cpu-thermal", "zenpower", "acpitz"):
        entries = temps.get(key)
        if entries:
            cur = getattr(entries[0], "current", None)
            if cur:
                return float(cur)
    for entries in temps.values():
        if entries:
            cur = getattr(entries[0], "current", None)
            if cur:
                return float(cur)
    return None


async def _alert_high_temp(ctemp: float) -> None:
    if not alert_group_id:
        return
    bots = list(nonebot.get_bots().values())
    if not bots:
        logger.warning("airi_mcrcon 高温告警无可用 bot 连接，已跳过")
        return
    text = (
        f"警告：服务器CPU温度过高！\n{ctemp} ℃\n"
        "请适当降低跑图频率，如果有高频红石或者科技正在运行也请歇一歇，"
        "公益开服，还请大家共同努力，维护服务器健康，谢谢大家！"
    )
    for bot in bots:
        try:
            await bot.send_group_msg(group_id=int(alert_group_id), message=text)
            return
        except Exception as e:
            logger.warning(f"airi_mcrcon 高温告警发送失败（{bot.self_id}）: {e}")


async def clear_item():
    cleared = None
    try:
        await rcon('say 即将在30s后清理掉落物')
        await asyncio.sleep(25)
        for i in range(5, 0, -1):
            await rcon(f'say 掉落物清理倒计时：{i}')
            await asyncio.sleep(1)
        msg = await rcon('kill @e[type=item]')
        m = re.search(r'(\d+)', msg or '')
        cleared = m.group(1) if m else None
        await rcon(f'say 已清理{cleared}个掉落物' if cleared else 'say 掉落物清理完成')
        result = "执行成功"
    except Exception as err:
        logger.warning(f"airi_mcrcon 掉落物清理失败: {err}")
        result = "出错了：" + str(err)

    try:
        ctemp = read_cpu_temp()
        if ctemp is not None and ctemp > 84.9:
            await _alert_high_temp(ctemp)
    except Exception as err:
        logger.warning(f"airi_mcrcon 温度检查失败: {err}")
    return result


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
    except Exception as e:
        logger.error(f"airi_mcrcon 绑定数据加载失败: {e}")
    try:
        await load_translate()
    except Exception as e:
        logger.error(f"airi_mcrcon 翻译开关加载失败: {e}")
    try:
        await _run_rcon(_sync_reconnect)
        logger.info("airi_mcrcon RCON 已连接")
    except Exception as e:
        logger.warning(f"airi_mcrcon RCON 连接失败（指令使用时会重连）: {e}")


@driver.on_shutdown
async def _():
    try:
        mcr.force_close()
    except Exception:
        pass
    shutdown_executor()



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
/pokebag @群友 ：查看群友背包内的宝可梦
/translate on|off ：【管理员】开启/关闭服务器输出翻译'''

async def _in_whitelist_group(ev: MessageEvent) -> bool:
    _, group_id = parse_session(ev)
    return group_id is not None and group_id in whitelist_group_list


def _cq_unescape(text: str) -> str:
    return (text.replace('&#91;', '[').replace('&#93;', ']')
                .replace('&#44;', ',').replace('&amp;', '&'))


rcon_handle = on_startswith('/', priority=10, rule=_in_whitelist_group)
superuser_debug = on_startswith('mdebug ', priority=5, block=True, rule=to_me(), permission=SUPERUSER)


@rcon_handle.handle()
async def _(bot: Bot, ev: MessageEvent):
    global data, translate_groups
    user_id, gruop_id = parse_session(ev)

    src = _cq_unescape(str(ev.message)[1:].strip())
    is_superuser = user_id in driver.config.superusers

    if src == 'connect':
        try:
            async with _rcon_lock:
                await _run_rcon(_sync_reconnect)
            res = 'RCON已连接'
        except Exception as err:
            res = f"连接出错：{str(err)}"
        await rcon_handle.finish(res.strip())
    elif is_superuser and src == 'disconnect':
        try:
            mcr.force_close()
            res = 'RCON已下线'
        except Exception as err:
            res = f"出错了：{str(err)}"
        await rcon_handle.finish(res.strip())
    elif src == "help":
        await rcon_handle.finish(HELP_TEXT.strip())
    elif is_superuser and src.startswith('translate'):
        try:
            arg = src[9:].strip().lower()
            if arg not in ['on', 'off']:
                raise ValueError("指令用法：/translate on 或 /translate off")
            if arg == 'on':
                translate_groups[gruop_id] = True
                res = '已为本群开启服务器输出翻译'
            else:
                translate_groups.pop(gruop_id, None)
                res = '已为本群关闭服务器输出翻译'
            await save_translate()
        except Exception as err:
            res = f"{str(err)}"
        await rcon_handle.finish(res.strip())

    if not await check_alive():
        await rcon_handle.finish("服务器 RCON 暂时不可用，请稍后再试。", reply_message=True)

    if src.startswith('auth'):
        try:
            raw = src[4:].strip()
            if not raw:
                raise ValueError("指令用法：/auth 你的mc玩家名")
            if len(raw.split()) != 1:
                raise ValueError("指令用法：/auth 你的mc玩家名（玩家名不能含空格）")
            name = require_mc_name(raw)
            await _bind_account(user_id, name)
            res = '认证成功！\n你现在可以进入服务器了'
        except Exception as err:
            res = f"{str(err)}"
    elif src == 'unauth':
        try:
            await _unbind_account(user_id)
            res = '注销成功'
        except Exception as err:
            res = f"{str(err)}"
    elif src == 'login':
        try:
            account = require_account(user_id)
            username = require_mc_name(account["username"])
            await rcon(f'execute as {username} run login {account["password"]}')
            res = '登录成功'
        except Exception as err:
            res = f"{str(err)}"
    elif src == 'banlist':
        try:
            await rcon("banhammer export_all_punishments")
            file_path = os.path.join(server_path, "banhammer_exports.json")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    datab = json.load(f)
                ban_records = datab.get('active', [])
                if not len(ban_records):
                    raise ValueError("当前封神榜为空")
                output_lines = []
                for record in ban_records:
                    player_name = str(record.get('playerName') or '未知玩家')
                    masked = (
                        f"{player_name[0]}***{player_name[-1]}"
                        if len(player_name) >= 2 else (player_name or "***")
                    )
                    reason = record.get('reason', '无原因')
                    ban_time = record.get('time', 0)
                    duration = record.get('duration', 0)
                    permanent = duration is None or int(duration) < 0
                    unban_time = ban_time + (duration or 0)
                    ban_time_str = await timestamp_to_datetime(ban_time)
                    duration_str = "永久封禁" if permanent else await format_duration(duration)
                    unban_time_str = "-" if permanent else await timestamp_to_datetime(unban_time)
                    output_lines.extend([
                        f"玩家名：{masked}",
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
            res = await rcon(src)
        except Exception as err:
            res = f"{str(err)}"
    elif src == "playerspawn":
        try:
            username = require_mc_name(require_account(user_id)["username"])
            res = await rcon(f'execute at {username} run {src}')
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
            from_user = require_mc_name(require_account(user_id)["username"])
            target = parse_at_qq(src[3:].strip(), "指令用法：/tpa @群友")
            to_user = require_mc_name(require_account(target, "对方未绑定游戏账户")["username"])
            res = await rcon(f'tp {from_user} {to_user}')
        except Exception as err:
            res = f"{str(err)}"
    elif src.startswith('locate'):
        try:
            username = require_mc_name(require_account(user_id)["username"])
            arg = src[6:].strip()
            if not re.fullmatch(r"[A-Za-z0-9_:# .\-]*", arg):
                raise ValueError("locate 参数含非法字符")
            res = await rcon(f'execute at {username} run locate {arg}'.strip())
        except Exception as err:
            res = f"{str(err)}"
    elif is_superuser and src == "clearitem":
        try:
            res = await clear_item()
        except Exception as err:
            res = f"{str(err)}"
    elif is_superuser:
        try:
            src = re.sub(
                r'\[CQ:at,\s*qq=(\d+)\]',
                lambda x: require_mc_name(data[x.group(1)]["username"]),
                src,
            )
            res = await rcon(src)
        except Exception as err:
            res = f"{str(err)}"
    else:
        # res = "你没有权限执行该指令"
        return

    out = res.rstrip() if len(res) else "执行成功（输出为空）"
    if translate_groups.get(gruop_id):
        out = await translate_to_chinese(out)
    await rcon_handle.finish(out, reply_message=True)


@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    global data
    if not _2fa_key:
        await superuser_debug.finish('未配置 _2fa_key，调试通道已禁用')

    user_id, gruop_id = parse_session(ev)

    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  ", " ")) != src:
        src = tmpa

    if not totp_verify(_2fa_key, src[:6]):
        await superuser_debug.finish('2fa verification failed')
    src = src[6:].strip()
    if not src:
        await superuser_debug.finish('缺少要执行的表达式')

    is_await = src[:6] == 'await '
    expr = src[6:].lstrip() if is_await else src
    ctx = {**globals(), 'bot': bot, 'ev': ev}
    try:
        try:
            code = compile(expr, '<mdebug>', 'eval')
            res = eval(code, ctx)
        except SyntaxError:
            code = compile(expr, '<mdebug>', 'exec')
            res = exec(code, ctx)
        if is_await and hasattr(res, '__await__'):
            res = await res
        res = '命令执行成功' if not res else str(res)
    except Exception:
        res = traceback.format_exc()

    await superuser_debug.finish(res, reply_message=True)
