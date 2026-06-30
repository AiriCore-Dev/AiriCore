import asyncio
import base64
import io
import zipfile
from datetime import datetime

import httpx
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.log import logger

packpic = on_command("packpic", block=True)


@packpic.handle()
async def handle_packpic(bot: Bot, event: GroupMessageEvent):
    # 1. 必须是引用（回复）某条消息
    if event.reply is None:
        await packpic.finish("请引用一条合并转发消息后再使用 packpic。")

    # 2. 从被引用的消息里找出 forward 段，拿到合并转发 id
    forward_id = None
    for seg in event.reply.message:
        if seg.type == "forward":
            forward_id = seg.data.get("id")
            break

    if forward_id is None:
        await packpic.finish("引用的消息不是合并转发消息。")

    # 3. 递归提取所有图片 / 图片表情的 url
    try:
        forward = await bot.get_forward_msg(id=forward_id)
    except ActionFailed as e:
        logger.opt(exception=e).error("获取合并转发消息失败")
        await packpic.finish("获取合并转发消息失败，请稍后再试。")

    urls: list[str] = []
    await _extract_images(bot, forward.get("messages", []), urls)

    # 去重并保持顺序
    urls = list(dict.fromkeys(urls))

    if not urls:
        await packpic.finish("没有在合并转发消息里找到图片。")

    # 4. 并发下载到内存
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        results = await asyncio.gather(
            *(_download(client, url) for url in urls),
            return_exceptions=True,
        )

    images: list[bytes] = []
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning(f"第 {idx} 张图片下载失败: {r}")
            continue
        if r:
            images.append(r)

    if not images:
        await packpic.finish("所有图片都下载失败了。")

    # 5. 在内存中打包成 zip
    zip_bytes = _make_zip(images)

    # 6. 通过 base64 上传到群（不落地本地文件）
    b64 = base64.b64encode(zip_bytes).decode()
    filename = f"pack_{datetime.now():%Y%m%d_%H%M%S}.zip"
    try:
        await bot.upload_group_file(
            group_id=event.group_id,
            file=f"base64://{b64}",
            name=filename,
        )
    except ActionFailed as e:
        logger.opt(exception=e).error("上传群文件失败")
        await packpic.finish(
            "打包完成，但上传群文件失败。请确认协议端支持 base64 上传文件。"
        )

    await packpic.finish(f"已打包 {len(images)} 张图片：{filename}")


async def _extract_images(bot: Bot, messages: list, collected: list[str]) -> None:
    """递归遍历合并转发节点，收集图片 / 图片表情的 url。"""
    for node in messages:
        # 不同协议端字段名可能是 content 或 message
        content = node.get("content") or node.get("message") or []
        for seg in content:
            seg_type = seg.get("type") if isinstance(seg, dict) else seg.type
            seg_data = seg.get("data") if isinstance(seg, dict) else seg.data
            seg_data = seg_data or {}

            if seg_type in ("image", "mface"):
                # image：普通图片；mface：商城图片表情
                url = seg_data.get("url") or seg_data.get("file")
                if url and str(url).startswith(("http://", "https://")):
                    collected.append(url)
            elif seg_type == "forward":
                # 嵌套的合并转发，继续展开
                nested_id = seg_data.get("id")
                if nested_id:
                    try:
                        nested = await bot.get_forward_msg(id=nested_id)
                        await _extract_images(
                            bot, nested.get("messages", []), collected
                        )
                    except ActionFailed:
                        logger.warning(f"展开嵌套转发失败: {nested_id}")


async def _download(client: httpx.AsyncClient, url: str) -> bytes:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


def _guess_ext(data: bytes) -> str:
    """根据文件头判断扩展名。"""
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
