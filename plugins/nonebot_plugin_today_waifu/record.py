import json
import hashlib
from typing import Union, Any
from pathlib import Path

import httpx
import nonebot
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import MessageSegment, Message

from .config import Config
from . import cache

driver = get_driver()
global_config = nonebot.get_driver().config
waifu_config: Config = Config.parse_obj(global_config.dict())
record_dir: Path = waifu_config.today_waifu_record_dir

TodayWaifuRecord = {}


@driver.on_startup
async def today_waifu_init() -> None:
    if not record_dir.exists():
        record_dir.mkdir(parents=True, exist_ok=True)
    for file in record_dir.glob('*.json'):
        TodayWaifuRecord[file.stem] = load_json(file)


@driver.on_shutdown
async def today_waifu_shutdown() -> None:
    cache.flush()


def save_json(data, json_file_path: Union[str, Path]) -> None:
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=False, indent=2)


def load_json(json_file_path: Union[str, Path]) -> Any:
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def clear_group_record(gid: str) -> None:
    if gid not in TodayWaifuRecord:
        return
    TodayWaifuRecord[gid].clear()
    save_group_record(gid, TodayWaifuRecord[gid])


def get_group_record(gid: str) -> dict:
    if gid in TodayWaifuRecord:
        return TodayWaifuRecord[gid]
    filename = record_dir / f'{gid}.json'
    if not filename.exists():
        save_json({}, filename)
    record = load_json(filename)
    TodayWaifuRecord[gid] = record
    return record


def save_group_record(gid: str, record: dict) -> None:
    record_file_path = record_dir / f'{gid}.json'
    save_json(record, record_file_path)


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
