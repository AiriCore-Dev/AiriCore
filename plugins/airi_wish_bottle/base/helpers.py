import base64
import hashlib
import re
import httpx

from openai import AsyncOpenAI

from utils import llm_fallback

from . import state
from .image_security import is_safe_url, validate_image_format, MAX_IMAGE_SIZE

client = AsyncOpenAI(
    api_key=getattr(state.driver.config, "llm_api_key", ""),
    base_url=getattr(state.driver.config, "llm_base_url", ""),
)

weijinci_prompt = '你是一个内容安全审核员。请判断用户输入的文本和图片（如有）是否包含违规内容（政治敏感、色情、暴力、违法犯罪、辱骂攻击、广告引流、涉及未成年人不良信息等）。如果包含任何违规内容，只回复数字1；如果内容合规，只回复数字0。不要输出任何其他文字。'


_CQ_RE = re.compile(r"\[CQ:[^\]]*\]")


def strip_cq(text: str) -> str:
    text = _CQ_RE.sub("", str(text or ""))
    text = (text.replace("&#91;", "[").replace("&#93;", "]")
                .replace("&#44;", ",").replace("&amp;", "&"))
    return _CQ_RE.sub("", text).strip()


async def parse_session(bot, ev):
    session_id = str(ev.get_session_id())
    if 'group' not in session_id:
        return None, None, None
    split_id = session_id.split("_")
    user_id = split_id[2]
    gruop_id = split_id[1]
    try:
        info = await bot.get_group_member_info(group_id=gruop_id, user_id=user_id)
        user_nick = info.get("card") or info.get("nickname") or user_id
    except Exception:
        user_nick = user_id
    return user_id, gruop_id, user_nick


async def check_weijinci(text, images=None):
    try:
        if images:
            content_parts = []
            if text:
                content_parts.append({"type": "text", "text": text})
            for img_b64 in images:
                if img_b64.startswith("base64://"):
                    img_data = img_b64[9:]
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}
                    })
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
            max_completion_tokens=4096,
            temperature=0.1,
            top_p=0.1,
            stream=False,
            stop=None,
            frequency_penalty=0,
            presence_penalty=0.1,
        )
        return 1 if '1' in answer else 0
    except Exception:
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


def add_bottle(unique_id, owner=-1, owner_id=-1, content=-1, comments=-1, times=-1, images=-1):
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
        data['bottles'][unique_id] = {
            "owner": str(owner), "owner_id": owner_id, "content": str(content),
            "comments": list(comments), "times": int(times), "images": list(images),
        }
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
    data['bottles'][unique_id] = bottle_tmp

    new_lst = _collection_of(data, bottle_tmp['owner_id'])
    if unique_id not in new_lst:
        new_lst.append(unique_id)


def delete_bottle(unique_id):
    data = state.data
    bottle = data.get('bottles', {}).get(unique_id)
    if bottle is None:
        return
    owner_id = str(bottle.get('owner_id', ''))
    data['bottles'].pop(unique_id, None)
    lst = data.setdefault('collections', {}).get(owner_id)
    if isinstance(lst, list):
        while unique_id in lst:
            lst.remove(unique_id)


def sync_bottle():
    collections = {}
    for key, bottle in state.data.get("bottles", {}).items():
        user_id = str(bottle.get('owner_id', ''))
        collections.setdefault(user_id, []).append(key)
    state.data["collections"] = collections


def send_email(dest, subject, text, html_body=None):
    state.email_list.append([dest, subject, text, html_body])


_IMAGE_RE = re.compile(r"\[CQ:image,file=([^,\]]+)(?:,url=([^,\]]+))?[^\]]*\]")


def extract_images(message_str: str) -> list[str]:
    images = []
    for match in _IMAGE_RE.finditer(message_str):
        url = match.group(2)
        if url:
            images.append(url)
    return images


async def download_image_as_base64(url: str) -> str | None:
    if not is_safe_url(url):
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            async with client.stream('GET', url) as resp:
                resp.raise_for_status()

                content_type = resp.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    return None

                chunks = []
                total_size = 0
                async for chunk in resp.aiter_bytes():
                    total_size += len(chunk)
                    if total_size > MAX_IMAGE_SIZE:
                        return None
                    chunks.append(chunk)

                image_bytes = b''.join(chunks)

                if not validate_image_format(image_bytes):
                    return None

                b64 = base64.b64encode(image_bytes).decode('utf-8')
                return f"base64://{b64}"
    except Exception:
        return None


async def process_images_from_message(message_str: str) -> list[str]:
    urls = extract_images(message_str)
    tasks = [download_image_as_base64(url) for url in urls]
    results = []
    for coro in tasks:
        result = await coro
        if result:
            results.append(result)
    return results
