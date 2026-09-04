import asyncio
import base64
import io
import zipfile
from datetime import datetime

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.log import logger

from utils.network import is_public_url_async
from utils.network import download_public_bytes
from utils.copy import COPY
from utils import credit
from utils.credit import PACKPIC_COST, charge_or_finish

MAX_IMAGES = 200
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_ZIP_BYTES = 80 * 1024 * 1024
MAX_FORWARD_DEPTH = 5
DOWNLOAD_CONCURRENCY = 8

packpic = on_command("packpic", block=True)


@packpic.handle()
async def handle_packpic(bot: Bot, event: GroupMessageEvent):
    if event.reply is None:
        await packpic.finish("请引用一条合并转发消息后再使用 packpic。")

    forward_id = None
    for seg in event.reply.message:
        if seg.type == "forward":
            forward_id = seg.data.get("id")
            break

    if forward_id is None:
        await packpic.finish("引用的消息不是合并转发消息。")

    try:
        forward = await bot.get_forward_msg(id=forward_id)
    except Exception as e:
        logger.opt(exception=e).error("获取合并转发消息失败")
        await packpic.finish(f"获取合并转发消息失败，{COPY['TRY_LATER']}")

    urls: list[str] = []
    await _extract_images(bot, forward.get("messages", []), urls, set(), 0)

    urls = list(dict.fromkeys(urls))
    truncated = len(urls) > MAX_IMAGES
    urls = urls[:MAX_IMAGES]

    if not urls:
        await packpic.finish("没有在合并转发消息里找到图片。")

    safe_urls = []
    for url in urls:
        if await is_public_url_async(url):
            safe_urls.append(url)
    blocked = len(urls) - len(safe_urls)
    if not safe_urls:
        await packpic.finish("图片地址均不可访问，已拒绝下载。")

    sem = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)
    images, oversize, total_truncated = await _download_images_limited(safe_urls, sem)
    truncated = truncated or total_truncated

    if not images:
        await packpic.finish("所有图片都下载失败了。")

    zip_bytes = _make_zip(images)
    if len(zip_bytes) > MAX_ZIP_BYTES:
        await packpic.finish(
            f"打包结果 {len(zip_bytes) // 1048576}MB 超过上限，请减少图片数量后重试。"
        )

    receipt = await charge_or_finish(packpic, event.get_user_id(), PACKPIC_COST)
    b64 = base64.b64encode(zip_bytes).decode()
    filename = f"pack_{datetime.now():%Y%m%d_%H%M%S}.zip"
    try:
        await bot.upload_group_file(
            group_id=event.group_id,
            file=f"base64://{b64}",
            name=filename,
        )
    except Exception as e:
        await credit.refund(receipt)
        logger.opt(exception=e).error("上传群文件失败")
        await packpic.finish(
            "打包完成，但上传群文件失败。请确认协议端支持 base64 上传文件。"
        )

    tips = []
    if truncated:
        tips.append("部分图片因数量或体积上限未被打包")
    if blocked:
        tips.append(f"{blocked} 个地址不可访问已跳过")
    if oversize:
        tips.append(f"{oversize} 张图片超过单张上限已跳过")
    tail = "（" + "；".join(tips) + "）" if tips else ""
    await packpic.finish(f"已打包 {len(images)} 张图片：{filename}{tail}")


async def _extract_images(
    bot: Bot, messages: list, collected: list[str], seen_ids: set, depth: int
) -> None:
    if depth > MAX_FORWARD_DEPTH or len(collected) >= MAX_IMAGES:
        return
    for node in messages:
        content = node.get("content") or node.get("message") or []
        for seg in content:
            seg_type = seg.get("type") if isinstance(seg, dict) else seg.type
            seg_data = seg.get("data") if isinstance(seg, dict) else seg.data
            seg_data = seg_data or {}

            if seg_type in ("image", "mface"):
                url = seg_data.get("url") or seg_data.get("file")
                if url and str(url).startswith(("http://", "https://")):
                    collected.append(url)
                    if len(collected) >= MAX_IMAGES:
                        return
            elif seg_type == "forward":
                nested_id = seg_data.get("id")
                if nested_id and str(nested_id) not in seen_ids:
                    seen_ids.add(str(nested_id))
                    try:
                        nested = await bot.get_forward_msg(id=nested_id)
                        await _extract_images(
                            bot, nested.get("messages", []), collected,
                            seen_ids, depth + 1,
                        )
                    except ActionFailed:
                        logger.warning(f"展开嵌套转发失败: {nested_id}")


async def _download(url: str, sem: asyncio.Semaphore) -> bytes:
    async with sem:
        return await download_public_bytes(
            url,
            MAX_IMAGE_BYTES,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )


async def _iter_download_batches(urls: list[str], sem: asyncio.Semaphore):
    for start in range(0, len(urls), DOWNLOAD_CONCURRENCY):
        batch = urls[start:start + DOWNLOAD_CONCURRENCY]
        yield await asyncio.gather(
            *(_download(url, sem) for url in batch),
            return_exceptions=True,
        )


async def _download_images_limited(
    urls: list[str], sem: asyncio.Semaphore
) -> tuple[list[bytes], int, bool]:
    images = []
    total = 0
    oversize = 0
    processed = 0
    async for results in _iter_download_batches(urls, sem):
        for result in results:
            processed += 1
            if isinstance(result, Exception):
                logger.warning(f"第 {processed} 张图片下载失败: {result}")
                continue
            if not result:
                continue
            if len(result) > MAX_IMAGE_BYTES:
                oversize += 1
                continue
            if total + len(result) > MAX_TOTAL_BYTES:
                return images, oversize, True
            images.append(result)
            total += len(result)
    return images, oversize, False


def _guess_ext(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:2] == b"BM":
        return "bmp"
    return "jpg"


def _make_zip(images: list[bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        width = len(str(len(images)))
        for i, data in enumerate(images, start=1):
            ext = _guess_ext(data)
            zf.writestr(f"{str(i).zfill(width)}.{ext}", data)
    return buffer.getvalue()
