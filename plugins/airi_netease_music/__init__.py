import base64
import asyncio

import httpx
from nonebot import on_command, require
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent
from utils import credit
from utils.credit import NETEASE_MUSIC_COST, charge_or_finish

require("nonebot_plugin_waiter")
from nonebot_plugin_waiter import waiter

SEARCH_API = "https://music.163.com/api/search/get/web"
OUTER_URL = "https://music.163.com/song/media/outer/url?id={sid}.mp3"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.163.com",
}
TOP_N = 5
SELECT_TIMEOUT = 60
MAX_AUDIO_BYTES = 4 * 1024 * 1024

netease_music = on_command("点歌", priority=50, block=True)


async def search_songs(keyword: str):
    params = {"s": keyword, "type": 1, "offset": 0, "limit": TOP_N}
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        resp = await client.get(SEARCH_API, params=params)
        resp.raise_for_status()
        data = resp.json()
    return (data.get("result") or {}).get("songs") or []


async def fetch_audio_b64(sid: int):
    url = OUTER_URL.format(sid=sid)
    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = await client.get(url)
    if resp.status_code != 200 or "audio" not in resp.headers.get("content-type", ""):
        return None, "unavailable"
    if len(resp.content) > MAX_AUDIO_BYTES:
        return None, "oversize"
    return base64.b64encode(resp.content).decode(), ""


def format_song(idx: int, song: dict) -> str:
    artists = "/".join(a.get("name", "") for a in song.get("artists", []))
    album = (song.get("album") or {}).get("name", "")
    return f"{idx}. {song.get('name', '未知')} - {artists}（{album}）"


@netease_music.handle()
async def handle_netease_music(bot: Bot, ev: MessageEvent, arg: Message = CommandArg()):
    keyword = arg.extract_plain_text().strip()
    if not keyword:
        await netease_music.finish("用法：点歌 歌曲名", reply_message=True)

    try:
        songs = await search_songs(keyword)
    except Exception:
        await netease_music.finish("搜索失败，网易云音乐接口可能暂时不可用，稍后再试吧~", reply_message=True)

    if not songs:
        await netease_music.finish(f"没有搜到「{keyword}」相关的歌曲呢~", reply_message=True)

    receipt = await charge_or_finish(netease_music, ev.get_user_id(), NETEASE_MUSIC_COST)

    listing = "\n".join(format_song(i + 1, s) for i, s in enumerate(songs))
    try:
        await netease_music.send(
            f"为你找到以下歌曲，请在 {SELECT_TIMEOUT} 秒内回复序号选择：\n{listing}",
            reply_message=True,
        )
    except Exception:
        await credit.refund(receipt)
        raise

    @waiter(waits=["message"], keep_session=True, block=True)
    async def get_choice(event: MessageEvent):
        return event.get_plaintext().strip()

    resp = await get_choice.wait(timeout=SELECT_TIMEOUT)
    if resp is None:
        await credit.refund(receipt)
        await netease_music.finish("超时啦，点歌已取消~")
    if not resp.isdigit() or not (1 <= int(resp) <= len(songs)):
        await credit.refund(receipt)
        await netease_music.finish("序号无效，点歌已取消~")

    song = songs[int(resp) - 1]
    sid = song["id"]

    try:
        await netease_music.send(MessageSegment.music("163", sid))
    except Exception:
        await credit.refund(receipt)
        raise

    try:
        audio_b64, reason = await fetch_audio_b64(sid)
    except Exception:
        audio_b64, reason = None, "unavailable"

    if audio_b64 is None:
        await credit.refund(receipt)
        if reason == "oversize":
            await netease_music.finish("这首歌文件过大，只能提供音乐卡片哦~")
        await netease_music.finish("这首歌可能受版权限制，无法获取音频哦~")

    try:
        await netease_music.send(MessageSegment.record(f"base64://{audio_b64}"))
    except Exception:
        await credit.refund(receipt)
        await netease_music.finish("语音发送失败了，可以直接点上面的音乐卡片收听~")
