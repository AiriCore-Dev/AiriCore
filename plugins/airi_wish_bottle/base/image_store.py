import asyncio
import base64
import os
import re
import secrets
import tempfile
from collections.abc import Iterable
from pathlib import Path

from nonebot import logger

from .image_security import MAX_IMAGE_SIZE, detect_image_type, validate_image_format


IMAGE_DIR = Path("data") / "airi_wish_bottle" / "images"
IMAGE_REF_PREFIX = "image://"
_IMAGE_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(?:png|jpeg|gif|webp)$")
_TEMP_PREFIX = ".image-"
_TEMP_SUFFIX = ".tmp"


def _name_from_ref(value: str) -> str | None:
    value = str(value or "")
    if not value.startswith(IMAGE_REF_PREFIX):
        return None
    name = value[len(IMAGE_REF_PREFIX):]
    return name if _IMAGE_NAME_RE.fullmatch(name) else None


def _path_from_ref(value: str) -> Path | None:
    name = _name_from_ref(value)
    return IMAGE_DIR / name if name else None


def _decode_base64(value: str) -> tuple[bytes, str]:
    if not isinstance(value, str) or not value.startswith("base64://"):
        raise ValueError("图片不是有效的 base64 数据")
    try:
        image_bytes = base64.b64decode(value[9:], validate=True)
    except Exception as e:
        raise ValueError("图片 base64 解码失败") from e
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ValueError("图片超过大小限制")
    image_type = detect_image_type(image_bytes)
    if image_type is None or not validate_image_format(image_bytes):
        raise ValueError("图片格式无效")
    return image_bytes, image_type


def _encode_base64(image_bytes: bytes) -> str:
    return "base64://" + base64.b64encode(image_bytes).decode("ascii")


def _write_image_sync(value: str) -> str:
    image_bytes, image_type = _decode_base64(value)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        name = f"{secrets.token_hex(16)}.{image_type}"
        destination = IMAGE_DIR / name
        if not destination.exists():
            break
    fd, temp_name = tempfile.mkstemp(
        dir=IMAGE_DIR,
        prefix=_TEMP_PREFIX,
        suffix=_TEMP_SUFFIX,
    )
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(image_bytes)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, destination)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return IMAGE_REF_PREFIX + name


def _delete_refs_sync(values: Iterable[str]) -> None:
    for value in set(values):
        path = _path_from_ref(value)
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"心愿瓶图片删除失败 {path.name}: {e}")


def _store_payload_sync(
    images: list[str], segments: list[dict]
) -> tuple[list[str], list[dict]]:
    image_segment_count = sum(
        1 for segment in segments
        if isinstance(segment, dict) and segment.get("type") == "image"
    )
    if image_segment_count and image_segment_count != len(images):
        raise ValueError("心愿瓶图片列表与图文顺序不一致")
    stored = []
    created = []
    try:
        for value in images:
            if _name_from_ref(value):
                stored.append(value)
                continue
            ref = _write_image_sync(value)
            stored.append(ref)
            created.append(ref)
        result_segments = []
        image_index = 0
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            result = dict(segment)
            if result.get("type") == "image":
                result["data"] = stored[image_index]
                image_index += 1
            result_segments.append(result)
        return stored, result_segments
    except Exception:
        _delete_refs_sync(created)
        raise


async def store_bottle_images(
    images: list[str], segments: list[dict]
) -> tuple[list[str], list[dict]]:
    return await asyncio.to_thread(
        _store_payload_sync,
        list(images or []),
        list(segments or []),
    )


def _read_image_sync(value: str) -> str | None:
    try:
        if isinstance(value, str) and value.startswith("base64://"):
            image_bytes, _ = _decode_base64(value)
            return _encode_base64(image_bytes)
        path = _path_from_ref(value)
        if path is None:
            return None
        image_bytes = path.read_bytes()
        if len(image_bytes) > MAX_IMAGE_SIZE or not validate_image_format(image_bytes):
            raise ValueError("磁盘图片格式无效")
        return _encode_base64(image_bytes)
    except Exception as e:
        logger.warning(f"心愿瓶图片读取失败: {e}")
        return None


async def read_image(value: str) -> str | None:
    return await asyncio.to_thread(_read_image_sync, value)


async def delete_image_refs(values: Iterable[str]) -> None:
    await asyncio.to_thread(_delete_refs_sync, list(values))


def record_image_refs(record: dict | None) -> set[str]:
    if not isinstance(record, dict):
        return set()
    refs = set()
    for value in record.get("images", []):
        if _name_from_ref(value):
            refs.add(value)
    for segment in record.get("segments", []):
        if not isinstance(segment, dict) or segment.get("type") != "image":
            continue
        value = segment.get("data")
        if _name_from_ref(value):
            refs.add(value)
    return refs


def _cleanup_orphans_sync(data: dict) -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    referenced = set()
    for section in ("bottles", "pending_bottles"):
        records = data.get(section, {})
        if not isinstance(records, dict):
            continue
        for record in records.values():
            referenced.update(record_image_refs(record))
    referenced_names = {
        name for value in referenced
        if (name := _name_from_ref(value)) is not None
    }
    for path in IMAGE_DIR.iterdir():
        name = path.name
        managed = _IMAGE_NAME_RE.fullmatch(name) is not None
        temporary = name.startswith(_TEMP_PREFIX) and name.endswith(_TEMP_SUFFIX)
        if not temporary and (not managed or name in referenced_names):
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"心愿瓶孤儿图片删除失败 {name}: {e}")


async def cleanup_orphans(data: dict) -> None:
    await asyncio.to_thread(_cleanup_orphans_sync, data)
