import base64
from typing import Any
from uuid import UUID


MAX_IMAGES = 8
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def validate_response(payload: Any, request_id: UUID) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("后端响应格式无效")
    if str(payload.get("request_id")) != str(request_id):
        raise ValueError("后端响应请求编号不匹配")
    if not isinstance(payload.get("ok"), bool):
        raise ValueError("后端响应状态无效")
    response_type = payload.get("type")
    if response_type not in ("text", "image"):
        raise ValueError("后端响应类型无效")
    text = payload.get("text")
    images = payload.get("images")
    if not isinstance(text, str) or not isinstance(images, list) or len(images) > MAX_IMAGES:
        raise ValueError("后端响应内容无效")
    decoded = []
    for image in images:
        if not isinstance(image, str) or not image:
            raise ValueError("后端图片内容无效")
        try:
            decoded.append(base64.b64decode(image, validate=True))
        except Exception as error:
            raise ValueError("后端图片编码无效") from error
    if sum(len(item) for item in decoded) > MAX_IMAGE_BYTES:
        raise ValueError("后端图片总大小超限")
    if response_type == "image" and not text.strip():
        raise ValueError("图片响应缺少文本降级内容")
    return {"ok": payload["ok"], "type": response_type, "text": text, "images": images, "error_code": str(payload.get("error_code", ""))}
