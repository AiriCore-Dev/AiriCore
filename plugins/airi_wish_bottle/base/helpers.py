import base64
import hashlib
import re
from urllib.parse import urljoin

import httpx

from nonebot import logger
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from openai import AsyncOpenAI

from utils import llm_fallback, llm_usage
from utils.network import is_public_url_async
from utils.onebot_query import event_nickname

from . import state
from .image_security import (
    MAX_IMAGE_SIZE,
    detect_image_type,
    validate_image_format,
)
from .image_store import delete_image_refs, read_image, record_image_refs

client = AsyncOpenAI(
    api_key=getattr(state.driver.config, "llm_api_key", ""),
    base_url=getattr(state.driver.config, "llm_base_url", ""),
)

weijinci_prompt = '你是一个内容安全审核员。请判断用户输入的文本和图片（如有）是否包含违规内容（政治敏感、色情、暴力、违法犯罪、辱骂攻击、广告引流、涉及未成年人不良信息等）。如果包含任何违规内容，只回复数字1；如果内容合规，只回复数字0。不要输出任何其他文字。'


_CQ_RE = re.compile(r"\[CQ:[^\]]*\]")
_DATA_IMAGE_RE = re.compile(r"^data:image/[^;]+;base64,(.+)$", re.I | re.S)
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 3


def _unescape_cq(text: str) -> str:
    return (str(text or "").replace("&#44;", ",").replace("&#91;", "[")
            .replace("&#93;", "]").replace("&amp;", "&"))


def strip_cq(text: str) -> str:
    text = _CQ_RE.sub("", str(text or ""))
    text = _unescape_cq(text)
    return _CQ_RE.sub("", text).strip()


def _image_data_url(img_b64: str) -> str | None:
    if not img_b64.startswith("base64://"):
        return None
    try:
        image_bytes = base64.b64decode(img_b64[9:], validate=True)
    except Exception:
        return None
    image_type = detect_image_type(image_bytes)
    if image_type is None:
        return None
    return f"data:image/{image_type};base64,{img_b64[9:]}"


async def parse_session(bot, ev):
    session_id = str(ev.get_session_id())
    if 'group' not in session_id:
        return None, None, None
    split_id = session_id.split("_")
    user_id = split_id[2]
    group_id = split_id[1]
    user_nick = event_nickname(ev)
    return user_id, group_id, user_nick


async def check_weijinci(text, images=None):
    try:
        if images:
            content_parts = []
            if text:
                content_parts.append({"type": "text", "text": text})
            for img_b64 in images:
                image_url = _image_data_url(img_b64)
                if image_url:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    })
            if not content_parts:
                logger.warning("心愿瓶审核未收到有效的文本或图片")
                return 1
            messages = [
                {"role": "system", "content": weijinci_prompt},
                {"role": "user", "content": content_parts},
            ]
        else:
            messages = [
                {"role": "system", "content": weijinci_prompt},
                {"role": "user", "content": text},
            ]
        answer = await llm_fallback.call_with_fallback(
            client,
            messages,
            tag="wish_bottle_weijinci",
            usage_source=llm_usage.SOURCE_WISH_BOTTLE,
            max_completion_tokens=4096,
            temperature=0.1,
            top_p=0.1,
            stream=False,
            stop=None,
            frequency_penalty=0,
            presence_penalty=0.1,
        )
        if '0' in answer and '1' not in answer:
            return 0
        return 1
    except Exception as e:
        logger.warning(f"心愿瓶内容审核失败: {e}")
        return 1


decr = lambda x: "".join([hex(i)[2:] for i in list(base64.b64decode(x.encode()))])
encr = lambda ff: base64.b64encode(bytes([int(ff[i:i+2], 16) for i in range(0, len(ff), 2)])).decode()
nxcr = lambda x: encr(hex(int(decr(x), 16) + 1)[2:])


async def generate_unique_id(content):
    unique_id = encr(hashlib.md5(content.encode()).hexdigest()[:12])
    unique_id_list = list(state.data["bottles"].keys()) + list(state.data["pending_bottles"].keys())
    while unique_id in unique_id_list:
        unique_id = nxcr(unique_id)
    return unique_id


def _collection_of(data, owner_id):
    return data.setdefault('collections', {}).setdefault(str(owner_id), [])


def add_bottle(unique_id, owner=-1, owner_id=-1, content=-1, comments=-1, times=-1, images=-1, segments=-1):
    data = state.data
    bottle_tmp = data.setdefault('bottles', {}).get(unique_id)
    if bottle_tmp is None:
        if owner == -1 or owner_id == -1:
            raise ValueError("新建心愿瓶必须提供 owner 与 owner_id")
        owner_id = str(owner_id)
        if content == -1:
            content = ''
        if comments == -1:
            comments = []
        if times == -1:
            times = 0
        if images == -1:
            images = []
        bottle_tmp = {
            "owner": str(owner), "owner_id": owner_id, "content": str(content),
            "comments": list(comments), "times": int(times), "images": list(images),
        }
        if segments != -1:
            bottle_tmp["segments"] = list(segments)
        data['bottles'][unique_id] = bottle_tmp
        lst = _collection_of(data, owner_id)
        if unique_id not in lst:
            lst.append(unique_id)
        return

    old_owner_id = str(bottle_tmp.get("owner_id", ""))
    old_lst = _collection_of(data, old_owner_id)
    while unique_id in old_lst:
        old_lst.remove(unique_id)

    if owner != -1:
        bottle_tmp['owner'] = str(owner)
    if owner_id != -1:
        bottle_tmp['owner_id'] = str(owner_id)
    if content != -1:
        bottle_tmp['content'] = str(content)
    if comments != -1:
        bottle_tmp['comments'] = list(comments)
    if times != -1:
        bottle_tmp['times'] = int(times)
    if images != -1:
        bottle_tmp['images'] = list(images)
    if segments != -1:
        bottle_tmp['segments'] = list(segments)
    data['bottles'][unique_id] = bottle_tmp

    new_lst = _collection_of(data, bottle_tmp['owner_id'])
    if unique_id not in new_lst:
        new_lst.append(unique_id)


async def delete_bottle(unique_id):
    data = state.data
    bottle = data.get('bottles', {}).get(unique_id)
    if bottle is None:
        return
    image_refs = record_image_refs(bottle)
    owner_id = str(bottle.get('owner_id', ''))
    data['bottles'].pop(unique_id, None)
    lst = data.setdefault('collections', {}).get(owner_id)
    if isinstance(lst, list):
        while unique_id in lst:
            lst.remove(unique_id)
    await delete_image_refs(image_refs)


def sync_bottle():
    collections = {}
    for key, bottle in state.data.get("bottles", {}).items():
        user_id = str(bottle.get('owner_id', ''))
        collections.setdefault(user_id, []).append(key)
    state.data["collections"] = collections


def send_email(dest, subject, text, html_body=None):
    state.email_list.append([dest, subject, text, html_body])


_IMAGE_RE = re.compile(r"\[CQ:image[^\]]*,url=([^,\]]+)[^\]]*\]")


def _extract_image_items(message) -> list[dict]:
    if isinstance(message, str):
        return [{"url": _unescape_cq(match.group(1))}
                for match in _IMAGE_RE.finditer(message) if match.group(1)]
    items = []
    try:
        segments = iter(message)
    except TypeError:
        return items
    for segment in segments:
        if getattr(segment, "type", None) != "image":
            continue
        data = getattr(segment, "data", None)
        if isinstance(data, dict):
            items.append(dict(data))
    return items


def extract_images(message) -> list[str]:
    images = []
    for item in _extract_image_items(message):
        source = item.get("url") or item.get("file")
        if source:
            images.append(_unescape_cq(source))
    return images


async def replace_images_with_base64(message_str: str) -> tuple[str, list[str]]:
    raw_urls = [match.group(1) for match in _IMAGE_RE.finditer(message_str)
                if match.group(1)]
    if not raw_urls:
        return message_str, []

    logger.info(f"[wish_bottle] 发现 {len(raw_urls)} 张图片需要下载")
    url_to_base64 = {}
    successful_images = []

    for raw_url in raw_urls:
        url = _unescape_cq(raw_url)
        logger.info(f"[wish_bottle] 正在下载图片: {url[:80]}...")
        b64 = await download_image_as_base64(url)
        if b64:
            url_to_base64[raw_url] = b64
            successful_images.append(b64)
            logger.info(f"[wish_bottle] 图片下载成功，base64 长度: {len(b64)}")
        else:
            logger.warning(f"[wish_bottle] 图片下载失败: {url[:80]}...")

    result = message_str
    for url, b64 in url_to_base64.items():
        result = result.replace(f',url={url}', f',url={b64}')

    logger.info(f"[wish_bottle] 成功下载 {len(successful_images)}/{len(raw_urls)} 张图片")
    return result, successful_images


async def download_image_as_base64(url: str) -> str | None:
    current_url = _unescape_cq(url).strip()
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            for redirect_count in range(_MAX_REDIRECTS + 1):
                if not await is_public_url_async(current_url):
                    logger.warning(f"心愿瓶图片地址不安全: {current_url[:120]}")
                    return None
                async with client.stream('GET', current_url) as resp:
                    if resp.status_code in _REDIRECT_STATUSES:
                        location = resp.headers.get('location')
                        if not location or redirect_count >= _MAX_REDIRECTS:
                            logger.warning("心愿瓶图片重定向无效或次数过多")
                            return None
                        current_url = urljoin(current_url, location)
                        continue
                    resp.raise_for_status()
                    chunks = []
                    total_size = 0
                    async for chunk in resp.aiter_bytes():
                        total_size += len(chunk)
                        if total_size > MAX_IMAGE_SIZE:
                            logger.warning(f"心愿瓶图片超过 {MAX_IMAGE_SIZE} 字节限制")
                            return None
                        chunks.append(chunk)
                    image_bytes = b''.join(chunks)
                    if not validate_image_format(image_bytes):
                        content_type = resp.headers.get('content-type', '')
                        logger.warning(f"心愿瓶收到无效图片数据: {content_type or '未知类型'}")
                        return None
                    b64 = base64.b64encode(image_bytes).decode('utf-8')
                    return f"base64://{b64}"
    except Exception as e:
        logger.warning(f"心愿瓶图片下载失败: {type(e).__name__}: {e}")
        return None


def _normalize_embedded_image(source: str) -> str | None:
    source = str(source or "").strip()
    if source.startswith("base64://"):
        encoded = source[9:]
    else:
        match = _DATA_IMAGE_RE.match(source)
        if not match:
            return None
        encoded = match.group(1)
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except Exception:
        return None
    if len(image_bytes) > MAX_IMAGE_SIZE or not validate_image_format(image_bytes):
        return None
    return f"base64://{base64.b64encode(image_bytes).decode('utf-8')}"


async def _load_image_source(source) -> str | None:
    source = _unescape_cq(source).strip()
    embedded = _normalize_embedded_image(source)
    if embedded:
        return embedded
    if source.startswith(("http://", "https://")):
        return await download_image_as_base64(source)
    return None


async def _image_from_item(item: dict, bot=None) -> str | None:
    sources = []
    for key in ("url", "file"):
        source = item.get(key)
        if source and source not in sources:
            sources.append(source)
    for source in sources:
        image = await _load_image_source(source)
        if image:
            return image
    file_id = item.get("file")
    if bot is None or not file_id:
        return None
    try:
        info = await bot.get_image(file=file_id)
    except Exception as e:
        logger.warning(f"心愿瓶无法通过 OneBot 获取图片: {type(e).__name__}: {e}")
        return None
    if not isinstance(info, dict):
        return None
    for key in ("url", "file"):
        image = await _load_image_source(info.get(key))
        if image:
            return image
    return None


async def process_bottle_content(message, bot=None, command_pattern=None):
    segments = []
    images = []
    first_text = True
    try:
        message_segments = iter(message)
    except TypeError:
        message_segments = iter(())
    for segment in message_segments:
        segment_type = getattr(segment, "type", None)
        data = getattr(segment, "data", None)
        if segment_type == "text" and isinstance(data, dict):
            value = str(data.get("text", ""))
            if first_text:
                if command_pattern:
                    value = re.sub(command_pattern, "", value, count=1)
                first_text = False
            if value:
                segments.append({"type": "text", "data": value})
        elif segment_type == "image" and isinstance(data, dict):
            image = await _image_from_item(dict(data), bot)
            if image:
                images.append(image)
                segments.append({"type": "image", "data": image})
    text_indexes = [i for i, item in enumerate(segments) if item["type"] == "text"]
    if text_indexes:
        segments[text_indexes[0]]["data"] = segments[text_indexes[0]]["data"].lstrip()
        segments[text_indexes[-1]]["data"] = segments[text_indexes[-1]]["data"].rstrip()
    segments = [item for item in segments if item["data"]]
    pure_text = "".join(item["data"] for item in segments if item["type"] == "text").strip()
    return pure_text, images, segments


async def bottle_content_message(bottle):
    message = Message()
    segments = bottle.get("segments")
    if isinstance(segments, list):
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            segment_type = segment.get("type")
            data = segment.get("data")
            if segment_type == "text" and data:
                message.append(MessageSegment.text(str(data)))
            elif segment_type == "image" and data:
                image = await read_image(str(data))
                if image:
                    message.append(MessageSegment.image(image))
                else:
                    message.append(MessageSegment.text('【图片读取失败】'))
        return message
    message.extend(Message(str(bottle.get("content", ""))))
    for value in bottle.get("images", []):
        image = await read_image(value)
        if image:
            message.append(MessageSegment.image(image))
        else:
            message.append(MessageSegment.text('【图片读取失败】'))
    return message


async def process_images_from_message(message, bot=None) -> list[str]:
    items = _extract_image_items(message)
    results = []
    for item in items:
        result = await _image_from_item(item, bot)
        if result:
            results.append(result)
    if items and len(results) != len(items):
        logger.warning(f"心愿瓶成功解析 {len(results)}/{len(items)} 张图片")
    return results
