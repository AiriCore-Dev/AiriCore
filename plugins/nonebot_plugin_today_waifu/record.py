import time
import pickle
import hashlib
import threading
from pathlib import Path

import httpx
from nonebot import get_driver
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import MessageSegment, Message

from . import cache

driver = get_driver()

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nonebot_plugin_today_waifu"
_RECORD_FILE = _DATA_DIR / "record.pk"
_FLUSH_INTERVAL = 3.0

_lock = threading.Lock()
_persist: dict = {}
_persist_loaded = False
_last_flush = 0.0
_dirty = False


def _ensure_loaded() -> None:
    global _persist, _persist_loaded
    if _persist_loaded:
        return
    _persist_loaded = True
    if _RECORD_FILE.is_file():
        try:
            with open(_RECORD_FILE, "rb") as f:
                _persist = pickle.load(f)
            return
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>today_waifu record.pk 读取失败，已重置: {e}</y>")
    _persist = {}


def _flush_record(force: bool = False) -> None:
    global _last_flush, _dirty
    now = time.time()
    if not force and (not _dirty or now - _last_flush < _FLUSH_INTERVAL):
        return
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _RECORD_FILE.with_suffix(".pk.tmp")
        with open(tmp, "wb") as f:
            pickle.dump(_persist, f)
        tmp.replace(_RECORD_FILE)
        _last_flush = now
        _dirty = False
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>today_waifu record.pk 写入失败: {e}</y>")


def flush_record() -> None:
    with _lock:
        _flush_record(force=True)


@driver.on_startup
async def today_waifu_init() -> None:
    with _lock:
        _ensure_loaded()


@driver.on_shutdown
async def today_waifu_shutdown() -> None:
    flush_record()
    cache.flush()


def get_group_record(gid: str) -> dict:
    with _lock:
        _ensure_loaded()
        return _persist.setdefault(gid, {})


def save_group_record(gid: str, record: dict) -> None:
    global _dirty
    with _lock:
        _ensure_loaded()
        _persist[gid] = record
        _dirty = True
        _flush_record()


def clear_group_record(gid: str) -> None:
    global _dirty
    with _lock:
        _ensure_loaded()
        _persist.pop(gid, None)
        _dirty = True
        _flush_record()


async def construct_force_waifu_msg(member_info: dict, waifu_id: int, bot_id: int) -> Message:
    member_name = (member_info.get("card") or member_info.get("nickname") or waifu_id)
    img = await download_avatar(str(waifu_id))
    if waifu_id == bot_id:
        return MessageSegment.text(f'\n你强娶了Airi？！Airi不依！') + MessageSegment.image(img)
    return (
        MessageSegment.text(f'\n强娶成功！你今天的老婆是：')
        + MessageSegment.image(img)
        + MessageSegment.text(f'{member_name}\n不过今天不能再换老婆了哦~')
    )


async def construct_force_waifu_taken_msg(member_info: dict, owner_uid: str) -> Message:
    owner_name = (member_info.get("card") or member_info.get("nickname") or owner_uid)
    return Message(f'\nTa已经是 {owner_name} 的老婆了，抢不走的！')


async def construct_change_waifu_msg(member_info: dict, new_waifu_id: int, bot_id: int, times: int,
                                     limit_times: int) -> Message:
    if new_waifu_id == -1:
        return Message(f'\n渣男，Airi把你老婆没收了！')
    member_name = (member_info.get("card") or member_info.get("nickname") or new_waifu_id)
    img = await download_avatar(str(new_waifu_id))
    if new_waifu_id == bot_id:
        return MessageSegment.text(
            f'\n你今天的老婆是Airi哦~'
            f'\n千万不要把Airi换掉哦~（斜眼笑）') + MessageSegment.image(
            img)
    msg = MessageSegment.text('')
    return msg + MessageSegment.text(f'\n你今天的老婆是：') + MessageSegment.image(img) + MessageSegment.text(
        f'{member_name}') + MessageSegment.text(f'\n这或许是你最后一次当花花公子的机会了呢……' if times == limit_times - 1 else '')


async def construct_waifu_msg(member_info: dict, waifu_id: int, bot_id: int, is_first: bool) -> Message:
    if waifu_id == -1:
        return Message(f'\n渣男，Airi把你老婆没收了！')
    member_name = (member_info.get("card") or member_info.get("nickname") or waifu_id)
    img = await download_avatar(str(waifu_id))
    if waifu_id == bot_id:
        if is_first:
            return MessageSegment.text(f'\n你今天的老婆是Airi哦~\n打卡啦摩托！\n') + MessageSegment.image(img)
        else:
            return MessageSegment.text(f'\n你今天的老婆是Airi哦，不可以再有别人了呢~\n开始石见👀👀👀') + MessageSegment.image(img)

    if is_first:
        return MessageSegment.text(f'\n你今天的老婆是：') + MessageSegment.image(img) + MessageSegment.text(
            f'{member_name}')
    return MessageSegment.text(f'\n好好对待她哦~\n你今天的老婆是：') + MessageSegment.image(
        img) + MessageSegment.text(
        f'{member_name}')


async def download_avatar(uid: str) -> bytes:
    cached = cache.get_avatar(uid)
    if cached is not None:
        return cached
    url = f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=640"
    data = await download_url(url)
    if not data or hashlib.md5(data).hexdigest() == "acef72340ac0e914090bd35799f5594e":
        url = f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100"
        data = await download_url(url)
    if data:
        cache.put_avatar(uid, data)
    return data


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
