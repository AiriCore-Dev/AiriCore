from __future__ import annotations

import base64
import io
from typing import Any

from nonebot.adapters.onebot.v11 import Message, MessageSegment
from PIL import Image, ImageDraw


def png_to_base64(image: Image.Image | bytes) -> str:
    if isinstance(image, Image.Image):
        stream = io.BytesIO()
        image.convert("RGBA").save(stream, format="PNG")
        payload = stream.getvalue()
    elif isinstance(image, bytes):
        payload = image
    else:
        raise TypeError("图片必须是图像或字节")
    if not payload:
        raise ValueError("图片不能为空")
    return "base64://" + base64.b64encode(payload).decode("ascii")


def message_image(image: Image.Image | bytes | str) -> MessageSegment:
    if isinstance(image, str):
        if not image.startswith("base64://") or len(image) <= len("base64://"):
            raise ValueError("图片必须使用 base64")
        try:
            decoded = base64.b64decode(image[len("base64://"):], validate=True)
            if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("图片格式无效")
        except Exception as exc:
            raise ValueError("图片格式无效") from exc
        value = image
    else:
        value = png_to_base64(image)
    return MessageSegment.image(value)


def text_fallback(message: str) -> MessageSegment:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("文字兜底不能为空")
    return MessageSegment.text(message.strip())


def _fallback_image(message: str) -> Image.Image:
    image = Image.new("RGBA", (960, 540), (26, 43, 67, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 936, 516), outline=(123, 196, 255, 255), width=4)
    draw.text((54, 54), "Airi · 王道征途", fill=(255, 255, 255, 255))
    draw.text((54, 108), message[:80], fill=(230, 242, 255, 255))
    return image


def render_response(message: str) -> Message:
    return Message(text_fallback(message)) + Message(message_image(_fallback_image(message)))
