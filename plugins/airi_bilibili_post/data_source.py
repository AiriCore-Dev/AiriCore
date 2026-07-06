# -*- coding: utf-8 -*-
"""B 站接口封装。

只依赖 httpx，全部异步。所有网络/解析都做防御式处理：出错返回 None 或空结构，
把异常上抛给调用方由其记录日志，绝不让定时任务因为一次接口抖动而崩掉。
"""
import time
import base64
import hashlib
import urllib.parse
from io import BytesIO
from typing import Optional

import httpx
from PIL import Image

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
# 桌面端 UA，缺省 UA 会被风控直接拒绝
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# 动态类型 -> 中文描述，用于推送文案
DYNAMIC_TYPE_NAME = {
    "DYNAMIC_TYPE_AV": "投稿视频",
    "DYNAMIC_TYPE_WORD": "动态",
    "DYNAMIC_TYPE_DRAW": "图文动态",
    "DYNAMIC_TYPE_ARTICLE": "专栏",
    "DYNAMIC_TYPE_FORWARD": "转发动态",
    "DYNAMIC_TYPE_LIVE_RCMD": "直播",
    "DYNAMIC_TYPE_PGC": "番剧",
    "DYNAMIC_TYPE_MUSIC": "音频",
    "DYNAMIC_TYPE_COMMON_SQUARE": "动态",
}

# WBI 混淆用的固定重排表（B 站前端硬编码）
_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def _headers(cookie: str = "") -> dict:
    h = {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
    }
    if cookie:
        # 从浏览器/配置里粘来的 cookie 常带换行或首尾空白，
        # httpx 会因非法 header 值直接抛 LocalProtocolError，这里清洗掉
        h["Cookie"] = cookie.replace("\r", "").replace("\n", "").strip()
    return h


async def fetch_image_b64(url: str) -> Optional[str]:
    """下载图片，压缩后返回 base64 字符串（不含 data: 前缀）。

    B 站图床 i*.hdslb.com 有防盗链，QQ 客户端直接拉 URL 会失败导致
    'rich media transfer failed'。改由我们带 Referer 拉下来内联发送。
    另外原图可能高达 4K / 数 MB，QQ 富媒体上传同样会失败，故统一压缩降尺寸。
    出错返回 None。
    """
    if not url:
        return None
    # 协议兜底
    if url.startswith("//"):
        url = "https:" + url
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=_headers(), timeout=15)
            resp.raise_for_status()
            raw = resp.content
    except Exception:
        return None
    return _compress_b64(raw)


def _compress_b64(raw: bytes, *, max_side: int = 1920, quality: int = 82) -> Optional[str]:
    """把图片字节压缩到合理尺寸并转 base64。压缩失败则退回原图 base64。"""
    try:
        img = Image.open(BytesIO(raw))
        # 处理透明通道：贴到白底再转 RGB，避免 JPEG 报错
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        # 限制最长边
        w, h = img.size
        if max(w, h) > max_side:
            if w >= h:
                img = img.resize((max_side, max(1, round(h * max_side / w))))
            else:
                img = img.resize((max(1, round(w * max_side / h)), max_side))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        # 兜底：压缩不了就发原图（小图无妨）
        try:
            return base64.b64encode(raw).decode()
        except Exception:
            return None


async def _get_json(client: httpx.AsyncClient, url: str, *, params: dict = None,
                    cookie: str = "") -> Optional[dict]:
    """GET 并返回 JSON；任何异常都上抛，由调用方处理。"""
    resp = await client.get(url, params=params, headers=_headers(cookie), timeout=10)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------- #
# 用户信息
# --------------------------------------------------------------------------- #
async def get_user_name(client: httpx.AsyncClient, uid: int, cookie: str = "") -> Optional[str]:
    """通过 UID 拿到 UP 主昵称。拿不到返回 None。"""
    try:
        data = await _get_json(
            client,
            "https://api.bilibili.com/x/space/wbi/acc/info",
            params={"mid": uid},
            cookie=cookie,
        )
        if data and data.get("code") == 0:
            return data["data"].get("name")
    except Exception:
        pass
    # 退路：关系接口一般不需要 WBI 签名
    try:
        data = await _get_json(
            client,
            "https://api.bilibili.com/x/web-interface/card",
            params={"mid": uid},
            cookie=cookie,
        )
        if data and data.get("code") == 0:
            return data["data"]["card"].get("name")
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- #
# 直播
# --------------------------------------------------------------------------- #
async def get_live_status(client: httpx.AsyncClient, uids: list, cookie: str = "") -> dict:
    """批量查询多个 UID 的直播间状态。

    返回 {uid(int): {"live_status": int, "title": str, "room_id": int,
                     "cover": str, "uname": str}}。
    live_status: 0 未开播 / 1 直播中 / 2 轮播。
    接口出错时抛异常。
    """
    if not uids:
        return {}
    data = await _post_json(
        client,
        "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids",
        json={"uids": [int(u) for u in uids]},
        cookie=cookie,
    )
    result = {}
    if data and data.get("code") == 0 and isinstance(data.get("data"), dict):
        for uid_str, info in data["data"].items():
            result[int(uid_str)] = {
                "live_status": int(info.get("live_status", 0)),
                "title": info.get("title", ""),
                "room_id": int(info.get("room_id", 0)),
                "cover": info.get("cover_from_user") or info.get("keyframe") or "",
                "uname": info.get("uname", ""),
            }
    return result


async def _post_json(client: httpx.AsyncClient, url: str, *, json: dict,
                     cookie: str = "") -> Optional[dict]:
    resp = await client.post(url, json=json, headers=_headers(cookie), timeout=10)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------- #
# WBI 签名
# --------------------------------------------------------------------------- #
def _get_mixin_key(orig: str) -> str:
    return "".join(orig[i] for i in _MIXIN_KEY_ENC_TAB)[:32]


async def _get_wbi_keys(client: httpx.AsyncClient, cookie: str = "") -> Optional[tuple]:
    """从 nav 接口拿 img_key / sub_key。失败返回 None。"""
    try:
        data = await _get_json(
            client, "https://api.bilibili.com/x/web-interface/nav", cookie=cookie
        )
        wbi = data["data"]["wbi_img"]
        img_url = wbi["img_url"]
        sub_url = wbi["sub_url"]
        img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
        sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]
        return img_key, sub_key
    except Exception:
        return None


def _enc_wbi(params: dict, img_key: str, sub_key: str) -> dict:
    """给 params 追加 wts / w_rid 签名字段。"""
    mixin_key = _get_mixin_key(img_key + sub_key)
    params = dict(params)
    params["wts"] = int(time.time())
    params = dict(sorted(params.items()))
    # 过滤掉 value 里的特殊字符
    params = {
        k: "".join(c for c in str(v) if c not in "!'()*")
        for k, v in params.items()
    }
    query = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params


# --------------------------------------------------------------------------- #
# 动态
# --------------------------------------------------------------------------- #
async def get_user_dynamics(client: httpx.AsyncClient, uid: int, cookie: str = "") -> list:
    """拉取某 UP 主的动态列表（新到旧）。

    返回 [{"id": str, "type": str, "type_name": str, "text": str,
           "pic": str, "ts": int, "url": str}]。
    需要 cookie（尤其 SESSDATA）才稳定，无 cookie 大概率被风控，此时返回空列表。
    """
    keys = await _get_wbi_keys(client, cookie)
    params = {
        "offset": "",
        "host_mid": uid,
        "timezone_offset": -480,
        "features": "itemOpusStyle",
    }
    if keys:
        params = _enc_wbi(params, keys[0], keys[1])
    data = await _get_json(
        client,
        "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space",
        params=params,
        cookie=cookie,
    )
    if not data or data.get("code") != 0:
        return []
    items = (data.get("data") or {}).get("items") or []
    result = []
    for it in items:
        parsed = _parse_dynamic_item(it)
        if parsed:
            result.append(parsed)
    return result


def _parse_dynamic_item(item: dict) -> Optional[dict]:
    """把单条动态原始 JSON 解析成推送需要的精简结构。结构异常返回 None。"""
    try:
        did = str(item.get("id_str") or item.get("id") or "")
        if not did:
            return None
        dtype = item.get("type", "")
        modules = item.get("modules") or {}
        author = modules.get("module_author") or {}
        ts = int(author.get("pub_ts") or 0)

        text = ""
        pic = ""
        dynamic = (modules.get("module_dynamic") or {})
        desc = dynamic.get("desc") or {}
        if desc:
            text = desc.get("text", "") or ""
        major = dynamic.get("major") or {}
        # 图文
        opus = major.get("opus") or {}
        if opus:
            if not text:
                summary = opus.get("summary") or {}
                text = summary.get("text", "") or ""
            pics = opus.get("pics") or []
            if pics:
                pic = pics[0].get("url", "") or ""
        # 视频投稿
        archive = major.get("archive") or {}
        if archive:
            if not text:
                text = archive.get("title", "") or ""
            pic = pic or archive.get("cover", "") or ""
        # 直播推荐
        live = major.get("live_rcmd") or {}

        type_name = DYNAMIC_TYPE_NAME.get(dtype, "动态")
        url = f"https://t.bilibili.com/{did}"
        return {
            "id": did,
            "type": dtype,
            "type_name": type_name,
            "text": text.strip(),
            "pic": pic,
            "ts": ts,
            "url": url,
        }
    except Exception:
        return None
